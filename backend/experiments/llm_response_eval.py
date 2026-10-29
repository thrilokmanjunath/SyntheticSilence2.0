"""
Cross-model evidence audit.

Several LLMs answer the same factual prompts; every answer is split into claims and each claim is
checked against retrieved sources by the same pipeline. The output is how often each model's claims
are backed up, refuted or left unsettled by sources.

What this is and is not:
- It measures agreement with retrievable sources, not truth. A "refuted" claim is one that
  retrieved sources push against; it can be wrong because the retriever or the checking model was.
- The checking model and retrievers are held fixed across responders, so differences between
  responders are not caused by the checker. A checker from the same vendor as one responder may still
  favour it; this is reported as a limitation, not corrected for.

Pure functions (aggregation, intervals, bootstrap, table rendering) are separate from the async runner
so they can be tested offline.
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import time
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Sequence, Tuple

VERDICTS = ["supported", "refuted", "mixed", "insufficient", "no_sources"]


@dataclass
class PromptItem:
    id: str
    category: str
    text: str


@dataclass
class ResponseRecord:
    model: str
    prompt_id: str
    category: str
    response: str
    error: Optional[str] = None


@dataclass
class ClaimRecord:
    model: str
    prompt_id: str
    category: str
    claim: str
    verdict: str                 # one of VERDICTS, or "error"
    sources_considered: int = 0
    sources_relevant: int = 0
    error: Optional[str] = None


# ---------- statistics ----------

def wilson_interval(successes: int, total: int, z: float = 1.96) -> Tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _rate(n: int, d: int) -> Dict[str, object]:
    lo, hi = wilson_interval(n, d)
    return {"n": n, "of": d, "rate": (n / d) if d else None, "ci95": [lo, hi]}


def summarize_model(
    claims: Sequence[ClaimRecord], responses: Sequence[ResponseRecord]
) -> Dict[str, object]:
    """Claim-level and response-level rates for one model."""
    ok = [c for c in claims if c.verdict != "error"]
    errors = len(claims) - len(ok)
    by_prompt: Dict[str, List[ClaimRecord]] = defaultdict(list)
    for c in ok:
        by_prompt[c.prompt_id].append(c)

    answered = [r for r in responses if r.error is None]
    # A response is only scored if it has at least one successfully checked claim.
    scored_prompts = [p for p, cs in by_prompt.items() if cs]

    out: Dict[str, object] = {
        "responses": len(responses),
        "responses_failed": len(responses) - len(answered),
        "responses_scored": len(scored_prompts),
        "claims_checked": len(ok),
        "claims_failed": errors,
        "claims_per_response": (len(ok) / len(scored_prompts)) if scored_prompts else None,
        "mean_sources": (sum(c.sources_considered for c in ok) / len(ok)) if ok else None,
        "claim_rates": {v: _rate(sum(1 for c in ok if c.verdict == v), len(ok)) for v in VERDICTS},
    }
    # Share of responses that contain at least one claim the sources push against.
    with_refuted = sum(1 for p in scored_prompts if any(c.verdict == "refuted" for c in by_prompt[p]))
    out["responses_with_refuted"] = _rate(with_refuted, len(scored_prompts))

    # Among claims that sources could settle either way, how many were backed up.
    decisive = [c for c in ok if c.verdict in ("supported", "refuted")]
    out["support_among_decisive"] = _rate(sum(1 for c in decisive if c.verdict == "supported"), len(decisive))

    by_cat: Dict[str, Dict[str, int]] = defaultdict(lambda: {"claims": 0, "supported": 0, "refuted": 0})
    for c in ok:
        by_cat[c.category]["claims"] += 1
        if c.verdict in ("supported", "refuted"):
            by_cat[c.category][c.verdict] += 1
    out["by_category"] = {k: dict(v) for k, v in sorted(by_cat.items())}
    return out


def summarize(
    claims: Sequence[ClaimRecord], responses: Sequence[ResponseRecord]
) -> Dict[str, Dict[str, object]]:
    models = sorted({r.model for r in responses} | {c.model for c in claims})
    return {
        m: summarize_model([c for c in claims if c.model == m], [r for r in responses if r.model == m])
        for m in models
    }


def bootstrap_difference(
    claims: Sequence[ClaimRecord],
    model_a: str,
    model_b: str,
    verdict: str = "refuted",
    iterations: int = 2000,
    seed: int = 7,
) -> Dict[str, object]:
    """
    Paired bootstrap over prompts of rate_a - rate_b for one verdict at claim level.

    Resampling prompts (not claims) respects that claims within one answer are not independent.
    Only prompts that both models answered successfully are used.
    """
    def per_prompt(model: str) -> Dict[str, List[str]]:
        d: Dict[str, List[str]] = defaultdict(list)
        for c in claims:
            if c.model == model and c.verdict != "error":
                d[c.prompt_id].append(c.verdict)
        return d

    a, b = per_prompt(model_a), per_prompt(model_b)
    shared = sorted(set(a) & set(b))
    if not shared:
        return {"prompts": 0, "diff": None, "ci95": None}

    def rate(d: Dict[str, List[str]], prompts: Iterable[str]) -> Optional[float]:
        vs = [v for p in prompts for v in d[p]]
        return (sum(1 for v in vs if v == verdict) / len(vs)) if vs else None

    point_a, point_b = rate(a, shared), rate(b, shared)
    if point_a is None or point_b is None:
        return {"prompts": len(shared), "diff": None, "ci95": None}

    rng = random.Random(seed)
    diffs: List[float] = []
    for _ in range(iterations):
        sample = [rng.choice(shared) for _ in shared]
        ra, rb = rate(a, sample), rate(b, sample)
        if ra is not None and rb is not None:
            diffs.append(ra - rb)
    diffs.sort()
    lo = diffs[int(0.025 * (len(diffs) - 1))]
    hi = diffs[int(0.975 * (len(diffs) - 1))]
    return {"prompts": len(shared), "diff": point_a - point_b, "ci95": [lo, hi]}


# ---------- rendering ----------

def _pct(x: Optional[float]) -> str:
    return "n/a" if x is None else f"{x * 100:.1f}"


def render_markdown(summary: Dict[str, Dict[str, object]], meta: Dict[str, object]) -> str:
    lines = [
        "# Cross-model evidence audit",
        "",
        f"- Prompts: {meta.get('prompts')}; checker model `{meta.get('checker_model')}`; variant `{meta.get('variant')}`",
        f"- Run id: `{meta.get('run_id')}`; started {meta.get('started')}",
        "- Verdicts are agreement with retrieved sources, not ground truth.",
        "",
        "| Model | Claims | Claims/answer | Supported % | Refuted % | Mixed % | Unsettled % | No sources % | Answers with a refuted claim % | Failed |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for model, s in summary.items():
        r = s["claim_rates"]  # type: ignore[index]
        wr = s["responses_with_refuted"]  # type: ignore[index]
        cpr = s["claims_per_response"]
        lines.append(
            f"| {model} | {s['claims_checked']} | {cpr:.1f} |" if cpr is not None else f"| {model} | {s['claims_checked']} | n/a |"
        )
        lines[-1] += (
            f" {_pct(r['supported']['rate'])} | {_pct(r['refuted']['rate'])} | {_pct(r['mixed']['rate'])} |"
            f" {_pct(r['insufficient']['rate'])} | {_pct(r['no_sources']['rate'])} | {_pct(wr['rate'])} |"
            f" {s['claims_failed']} |"
        )
    lines += ["", "95% Wilson intervals are in `summary.json`.", ""]
    return "\n".join(lines)


def render_latex_table(summary: Dict[str, Dict[str, object]]) -> str:
    rows = []
    for model, s in summary.items():
        r = s["claim_rates"]  # type: ignore[index]
        wr = s["responses_with_refuted"]  # type: ignore[index]
        name = model.split("/")[-1].replace("_", r"\_")
        rows.append(
            f"{name} & {s['claims_checked']} & {_pct(r['supported']['rate'])} & {_pct(r['refuted']['rate'])}"
            f" & {_pct(r['insufficient']['rate'])} & {_pct(r['no_sources']['rate'])} & {_pct(wr['rate'])} \\\\"
        )
    return "\n".join(rows)


# ---------- runner ----------

Responder = Callable[[str, PromptItem], Awaitable[str]]
Extractor = Callable[[str], Awaitable[List[str]]]
Checker = Callable[[str], Awaitable[Dict[str, object]]]


@dataclass
class Spend:
    read: Callable[[], float]


async def collect_responses(
    models: Sequence[str],
    prompts: Sequence[PromptItem],
    respond: Responder,
    out_path: Path,
    concurrency: int = 4,
    log: Callable[[str], None] = print,
) -> List[ResponseRecord]:
    """Asks every model every prompt. Resumable: finished (model, prompt) pairs are skipped."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    done: Dict[Tuple[str, str], ResponseRecord] = {}
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = ResponseRecord(**json.loads(line))
                if r.error is None:  # failures are retried on resume
                    done[(r.model, r.prompt_id)] = r
    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()

    async def one(model: str, p: PromptItem) -> None:
        if (model, p.id) in done:
            return
        async with gate:
            try:
                text = await respond(model, p)
                rec = ResponseRecord(model, p.id, p.category, text)
            except Exception as exc:  # noqa: BLE001  one failed model must not sink the run
                rec = ResponseRecord(model, p.id, p.category, "", error=f"{type(exc).__name__}: {str(exc)[:160]}")
        async with lock:
            if rec.error is None:
                done[(model, p.id)] = rec
            with open(out_path, "a", encoding="utf-8") as fh:
                fh.write(json.dumps(asdict(rec)) + "\n")

    await asyncio.gather(*(one(m, p) for m in models for p in prompts))
    # Last write per key wins; return only successful records plus current failures for reporting.
    final: Dict[Tuple[str, str], ResponseRecord] = {}
    for line in out_path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = ResponseRecord(**json.loads(line))
            final[(r.model, r.prompt_id)] = r
    log(f"responses: {sum(1 for r in final.values() if r.error is None)} ok, "
        f"{sum(1 for r in final.values() if r.error is not None)} failed")
    return list(final.values())


async def check_responses(
    responses: Sequence[ResponseRecord],
    extract: Extractor,
    check: Checker,
    out_path: Path,
    concurrency: int = 4,
    budget_ok: Callable[[], bool] = lambda: True,
    log: Callable[[str], None] = print,
) -> List[ClaimRecord]:
    """Splits every successful answer into claims and checks each. Resumable per answer."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    finished: Dict[Tuple[str, str], List[ClaimRecord]] = defaultdict(list)
    if out_path.exists():
        for line in out_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                c = ClaimRecord(**json.loads(line))
                finished[(c.model, c.prompt_id)].append(c)
    # An answer counts as finished only if none of its claims failed; failed ones are redone.
    redo = {k for k, cs in finished.items() if any(c.verdict == "error" for c in cs)}
    if redo:
        kept = [c for k, cs in finished.items() if k not in redo for c in cs]
        out_path.write_text("".join(json.dumps(asdict(c)) + "\n" for c in kept), encoding="utf-8")
        for k in redo:
            finished.pop(k)

    gate = asyncio.Semaphore(concurrency)
    lock = asyncio.Lock()
    stopped = {"budget": False}

    async def one(r: ResponseRecord) -> None:
        key = (r.model, r.prompt_id)
        if r.error is not None or key in finished:
            return
        async with gate:
            if stopped["budget"] or not budget_ok():
                stopped["budget"] = True
                return
            records: List[ClaimRecord] = []
            try:
                claims = await extract(r.response)
            except Exception as exc:  # noqa: BLE001
                records.append(ClaimRecord(r.model, r.prompt_id, r.category, "", "error",
                                           error=f"extract: {type(exc).__name__}: {str(exc)[:140]}"))
                claims = []
            for text in claims:
                try:
                    res = await check(text)
                    records.append(ClaimRecord(
                        r.model, r.prompt_id, r.category, text, str(res["verdict"]),
                        int(res.get("sources_considered", 0) or 0), int(res.get("sources_relevant", 0) or 0),
                    ))
                except Exception as exc:  # noqa: BLE001
                    records.append(ClaimRecord(r.model, r.prompt_id, r.category, text, "error",
                                               error=f"{type(exc).__name__}: {str(exc)[:140]}"))
        async with lock:
            finished[key] = records
            with open(out_path, "a", encoding="utf-8") as fh:
                for rec in records:
                    fh.write(json.dumps(asdict(rec)) + "\n")
            log(f"checked {r.model} / {r.prompt_id}: {len(records)} claims")

    await asyncio.gather(*(one(r) for r in responses))
    if stopped["budget"]:
        log("budget reached: run is incomplete; re-run with the same --run-id to continue")
    return [c for cs in finished.values() for c in cs]
