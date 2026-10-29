"""
Run the verdict validation harness against the live pipeline.

    python scripts/eval_verdict.py --variant pooled --n 150 --budget-usd 2
    python scripts/eval_verdict.py --variant stance_wiki --only-ids-from baseline_pooled_run1

Variants (verdict mode, retrievers):
    pooled          pooled NLI,   OpenAlex           the v1 baseline
    pooled_wiki     pooled NLI,   Wikipedia          isolates the retriever change
    stance_wiki     per-source,   Wikipedia          isolates stance + ranking on the same retriever
    stance_openalex per-source,   OpenAlex
    stance_both     per-source,   Wikipedia+OpenAlex

--only-ids-from restricts a run to the claims another run scored successfully, so two variants are
compared on identical claims.
"""
import argparse
import asyncio
import dataclasses
import datetime
import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "backend"))

from app.config import Settings  # noqa: E402
from app.container import build_pipeline  # noqa: E402
from app.models.claim import ExtractedClaim  # noqa: E402
from experiments.verdict_eval import CostMeter, RunConfig, run_eval, sample_fever  # noqa: E402

VARIANTS = {
    "pooled": ("pooled", ("openalex",)),
    "pooled_wiki": ("pooled", ("wikipedia",)),
    "stance_wiki": ("stance", ("wikipedia",)),
    "stance_openalex": ("stance", ("openalex",)),
    "stance_both": ("stance", ("wikipedia", "openalex")),
}


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def make_assessor(pipeline):
    async def assess(claim):
        a = await pipeline.assess_claim(ExtractedClaim(id=claim.id, original_text=claim.text, context="FEVER"))
        return {
            "verdict": a.verdict,
            "sources_considered": len(a.evidence),
            "sources_relevant": a.sources_relevant,
            "support": a.signal.semantic_support,
            "conflict": a.signal.contradiction_level,
        }
    return assess


def scored_ids(run_id: str) -> set:
    path = REPO / "results" / "verdict_eval" / run_id / "predictions.jsonl"
    ids = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if row.get("predicted") != "ERROR":
            ids.add(str(row["id"]))
    return ids


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="pooled", choices=sorted(VARIANTS))
    ap.add_argument("--n", type=int, default=150)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--budget-usd", type=float, default=2.0)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--run-id", default=None, help="Reuse a run id to resume")
    ap.add_argument("--retry-errors", action="store_true", help="With --run-id: re-run claims that errored")
    ap.add_argument("--only-ids-from", default=None, help="Run id whose successfully scored claims to use")
    ap.add_argument("--data", default=str(REPO / "data" / "raw" / "fever" / "paper_dev.jsonl"))
    args = ap.parse_args()

    mode, retrievers = VARIANTS[args.variant]
    settings = dataclasses.replace(Settings.from_env(), verdict_mode=mode, retrievers=retrievers)
    pipeline = build_pipeline(settings)
    provider = pipeline.claim_service.llm_provider

    claims = sample_fever(Path(args.data), args.n, args.seed)
    if args.only_ids_from:
        keep = scored_ids(args.only_ids_from)
        claims = [c for c in claims if c.id in keep]
        print(f"paired with {args.only_ids_from}: {len(claims)} claims")

    run_id = args.run_id or f"{args.variant}_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    out_dir = REPO / "results" / "verdict_eval" / run_id

    cost = CostMeter(read=lambda: {"prompt_tokens": provider.prompt_tokens, "completion_tokens": provider.completion_tokens})
    config = RunConfig(
        variant=args.variant, n=len(claims), seed=args.seed, model=settings.openrouter_model,
        concurrency=args.concurrency, budget_usd=args.budget_usd,
        extra={"git_sha": git_sha(), "verdict_mode": mode, "retrievers": list(retrievers),
               "paired_with": args.only_ids_from},
    )
    summary = await run_eval(
        claims, make_assessor(pipeline), config, out_dir, cost=cost, retry_errors=args.retry_errors
    )
    print((out_dir / "report.md").read_text(encoding="utf-8"))
    print(f"written to {out_dir}")
    if summary["incomplete"]:
        sys.exit(2)


if __name__ == "__main__":
    asyncio.run(main())
