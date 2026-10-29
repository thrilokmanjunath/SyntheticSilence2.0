"""
Verdict validation harness.

Measures how often the served user-facing verdict agrees with FEVER gold labels, so changes to
retrieval / stance / aggregation are accepted or rejected on numbers rather than impressions.

Pure functions (sampling, metrics) are separate from the async runner so they unit-test offline.

Caveats that every report repeats:
- FEVER claims are Wikipedia-derived and the LLM may have seen them; compare configs relatively.
- "NOT ENOUGH INFO" is not the same thing as "no source was found".
- N is small, so every rate carries a Wilson 95% interval.
"""
from __future__ import annotations

import asyncio
import json
import math
import random
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Awaitable, Callable, Dict, Iterable, List, Optional, Sequence

from app.services.verdict import VERDICT_TO_FEVER

GOLD_LABELS = ["SUPPORTS", "REFUTES", "NOT ENOUGH INFO"]
PRED_LABELS = GOLD_LABELS + ["MIXED"]


@dataclass
class EvalClaim:
    id: str
    text: str
    gold: str


@dataclass
class Prediction:
    id: str
    text: str
    gold: str
    verdict: str            # supported | refuted | mixed | insufficient | no_sources | error
    predicted: str          # FEVER-style label, MIXED, or ERROR
    sources_considered: int
    sources_relevant: int
    support: Optional[float] = None
    conflict: Optional[float] = None
    latency_s: float = 0.0
    error: Optional[str] = None


# A variant maps one claim to (verdict, considered, relevant, support, conflict).
Assessor = Callable[[EvalClaim], Awaitable[Dict]]


# ---------- sampling ----------

def sample_fever(path: Path, n: int, seed: int = 42) -> List[EvalClaim]:
    """Balanced sample over SUPPORTS / REFUTES / NOT ENOUGH INFO, deterministic for a given seed."""
    by_label: Dict[str, Dict[str, EvalClaim]] = {label: {} for label in GOLD_LABELS}
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            row = json.loads(line)
            label = row.get("label")
            claim = (row.get("claim") or "").strip()
            if label not in by_label or not claim:
                continue
            cid = str(row.get("id"))
            # The paper_dev file repeats a claim once per evidence annotation: keep one.
            by_label[label].setdefault(cid, EvalClaim(id=cid, text=claim, gold=label))

    per_class = n // len(GOLD_LABELS)
    rng = random.Random(seed)
    sample: List[EvalClaim] = []
    for label in GOLD_LABELS:
        pool = sorted(by_label[label].values(), key=lambda c: c.id)
        if len(pool) < per_class:
            raise ValueError(f"Only {len(pool)} {label} claims available, need {per_class}")
        sample.extend(rng.sample(pool, per_class))
    rng.shuffle(sample)
    return sample


# ---------- metrics ----------

def wilson_interval(successes: int, total: int, z: float = 1.96) -> tuple[float, float]:
    if total == 0:
        return (0.0, 0.0)
    p = successes / total
    denom = 1 + z * z / total
    centre = (p + z * z / (2 * total)) / denom
    half = z * math.sqrt(p * (1 - p) / total + z * z / (4 * total * total)) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def _prf(tp: int, predicted: int, actual: int) -> Dict[str, float]:
    precision = tp / predicted if predicted else 0.0
    recall = tp / actual if actual else 0.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return {"precision": precision, "recall": recall, "f1": f1}


def compute_metrics(predictions: Sequence[Prediction]) -> Dict:
    total = len(predictions)
    errors = sum(1 for p in predictions if p.predicted == "ERROR")
    scored = [p for p in predictions if p.predicted != "ERROR"]

    confusion = {g: {p: 0 for p in PRED_LABELS} for g in GOLD_LABELS}
    for p in scored:
        confusion[p.gold][p.predicted] += 1

    per_class = {}
    for label in GOLD_LABELS:
        tp = confusion[label][label]
        predicted = sum(confusion[g][label] for g in GOLD_LABELS)
        actual = sum(confusion[label].values())
        per_class[label] = {**_prf(tp, predicted, actual), "support": actual}

    correct = sum(confusion[g][g] for g in GOLD_LABELS)
    n = len(scored)
    lo, hi = wilson_interval(correct, n)

    decisive = [p for p in scored if p.gold in ("SUPPORTS", "REFUTES")]
    decisive_correct = sum(1 for p in decisive if p.predicted == p.gold)
    d_lo, d_hi = wilson_interval(decisive_correct, len(decisive))

    covered = sum(1 for p in scored if p.sources_relevant > 0)
    latencies = sorted(p.latency_s for p in scored)

    return {
        "n_total": total,
        "n_scored": n,
        "n_errors": errors,
        "accuracy": correct / n if n else 0.0,
        "accuracy_ci95": [lo, hi],
        "macro_f1": sum(per_class[l]["f1"] for l in GOLD_LABELS) / len(GOLD_LABELS),
        "decisive_accuracy": decisive_correct / len(decisive) if decisive else 0.0,
        "decisive_accuracy_ci95": [d_lo, d_hi],
        "coverage": covered / n if n else 0.0,
        "mixed_rate": sum(1 for p in scored if p.predicted == "MIXED") / n if n else 0.0,
        "per_class": per_class,
        "confusion": confusion,
        "median_latency_s": latencies[len(latencies) // 2] if latencies else 0.0,
    }


# ---------- runner ----------

@dataclass
class CostMeter:
    """Reads running totals from the provider so a budget can stop the run."""
    read: Callable[[], Dict[str, int]]
    usd_per_m_prompt: float = 0.15
    usd_per_m_completion: float = 0.60

    def usd(self) -> float:
        u = self.read()
        return (u["prompt_tokens"] * self.usd_per_m_prompt + u["completion_tokens"] * self.usd_per_m_completion) / 1e6


@dataclass
class RunConfig:
    variant: str
    n: int
    seed: int
    model: str
    concurrency: int = 4
    budget_usd: float = 2.0
    extra: Dict = field(default_factory=dict)


async def run_eval(
    claims: Sequence[EvalClaim],
    assess: Assessor,
    config: RunConfig,
    out_dir: Path,
    cost: Optional[CostMeter] = None,
    resume: bool = True,
    retry_errors: bool = False,
    log: Callable[[str], None] = print,
) -> Dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    pred_path = out_dir / "predictions.jsonl"

    done: Dict[str, Prediction] = {}
    if resume and pred_path.exists():
        for line in pred_path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                p = Prediction(**json.loads(line))
                if retry_errors and p.predicted == "ERROR":
                    continue
                done[p.id] = p
        log(f"resuming: {len(done)} predictions already on disk")
        if retry_errors:
            # Rewrite without the errors so the file never holds two rows for one claim.
            pred_path.write_text("".join(json.dumps(asdict(p)) + "\n" for p in done.values()), encoding="utf-8")

    todo = [c for c in claims if c.id not in done]
    gate = asyncio.Semaphore(config.concurrency)
    lock = asyncio.Lock()
    stopped = {"budget": False}

    async def one(claim: EvalClaim) -> None:
        async with gate:
            if stopped["budget"]:
                return
            if cost and cost.usd() >= config.budget_usd:
                stopped["budget"] = True
                log(f"budget ${config.budget_usd:.2f} reached, stopping")
                return
            started = time.perf_counter()
            try:
                result = await assess(claim)
                verdict = result["verdict"]
                pred = Prediction(
                    id=claim.id, text=claim.text, gold=claim.gold, verdict=verdict,
                    predicted=VERDICT_TO_FEVER[verdict],
                    sources_considered=result.get("sources_considered", 0),
                    sources_relevant=result.get("sources_relevant", 0),
                    support=result.get("support"), conflict=result.get("conflict"),
                    latency_s=time.perf_counter() - started,
                )
            except Exception as exc:  # noqa: BLE001  one bad claim must not sink the run
                pred = Prediction(
                    id=claim.id, text=claim.text, gold=claim.gold, verdict="error", predicted="ERROR",
                    sources_considered=0, sources_relevant=0,
                    latency_s=time.perf_counter() - started, error=f"{type(exc).__name__}: {str(exc)[:160]}",
                )
            async with lock:
                done[claim.id] = pred
                with open(pred_path, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(asdict(pred)) + "\n")
                if len(done) % 10 == 0:
                    log(f"{len(done)}/{len(claims)} done" + (f" (${cost.usd():.3f})" if cost else ""))

    await asyncio.gather(*(one(c) for c in todo))

    ordered = [done[c.id] for c in claims if c.id in done]
    metrics = compute_metrics(ordered)
    summary = {
        "config": asdict(config),
        "metrics": metrics,
        "cost_usd": cost.usd() if cost else None,
        "budget_stopped": stopped["budget"],
        "incomplete": len(ordered) < len(claims),
    }
    (out_dir / "metrics.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    (out_dir / "report.md").write_text(render_report(summary), encoding="utf-8")
    return summary


def render_report(summary: Dict) -> str:
    m, c = summary["metrics"], summary["config"]
    pct = lambda x: f"{x * 100:.1f}%"  # noqa: E731
    ci = lambda pair: f"{pct(pair[0])} to {pct(pair[1])}"  # noqa: E731
    lines = [
        f"# Verdict evaluation: {c['variant']}",
        "",
        f"- Sample: N={m['n_total']} (scored {m['n_scored']}, errors {m['n_errors']}), seed {c['seed']}, model `{c['model']}`",
        f"- Accuracy: {pct(m['accuracy'])} (95% CI {ci(m['accuracy_ci95'])})",
        f"- Macro-F1: {m['macro_f1']:.3f}",
        f"- Accuracy on SUPPORTS/REFUTES only: {pct(m['decisive_accuracy'])} (95% CI {ci(m['decisive_accuracy_ci95'])})",
        f"- Coverage (at least one relevant source): {pct(m['coverage'])}",
        f"- Mixed verdicts: {pct(m['mixed_rate'])}",
        f"- Median latency per claim: {m['median_latency_s']:.1f}s",
        f"- Cost: ${summary['cost_usd']:.3f}" if summary["cost_usd"] is not None else "- Cost: n/a",
    ]
    if summary["budget_stopped"] or summary["incomplete"]:
        lines.append("- WARNING: run is incomplete (budget stop or interruption); do not compare with full runs.")
    lines += ["", "## Per class", "", "| Gold | Precision | Recall | F1 | N |", "|---|---|---|---|---|"]
    for label, v in m["per_class"].items():
        lines.append(f"| {label} | {pct(v['precision'])} | {pct(v['recall'])} | {v['f1']:.3f} | {v['support']} |")
    lines += ["", "## Confusion (rows gold, columns predicted)", "", "| Gold | " + " | ".join(PRED_LABELS) + " |",
              "|---|" + "---|" * len(PRED_LABELS)]
    for g in GOLD_LABELS:
        lines.append(f"| {g} | " + " | ".join(str(m["confusion"][g][p]) for p in PRED_LABELS) + " |")
    lines += [
        "",
        "## Caveats",
        "",
        "- FEVER claims are Wikipedia-derived and the language model may have seen them; compare configurations relatively.",
        "- NOT ENOUGH INFO is not the same as no source found; a source-poor retriever lowers apparent NEI recall differently.",
        "- Small N gives wide intervals. Differences inside the intervals are not evidence of improvement.",
        "",
    ]
    return "\n".join(lines)
