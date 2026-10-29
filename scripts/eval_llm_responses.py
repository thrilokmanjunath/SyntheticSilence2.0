"""
Cross-model evidence audit: ask several LLMs the same questions, then check every claim in every
answer against retrieved sources with one fixed checker.

    python scripts/eval_llm_responses.py --dry-run
    python scripts/eval_llm_responses.py --budget-usd 3 --run-id audit1
    python scripts/eval_llm_responses.py --run-id audit1          # resume after an interruption

All models are reached through OpenRouter with the key in backend/.env. The checker is the model in
OPENROUTER_MODEL (default openai/gpt-4o-mini) and is the same for every responder.
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
from experiments.llm_response_eval import (  # noqa: E402
    PromptItem, bootstrap_difference, check_responses, collect_responses,
    render_latex_table, render_markdown, summarize,
)
from experiments.verdict_eval import CostMeter  # noqa: E402

# Responders. Edit freely: any OpenRouter model id works. Prices are USD per million tokens
# (input, output) and are only used for the budget estimate.
RESPONDERS = {
    "openai/gpt-4o": (2.50, 10.00),
    "anthropic/claude-sonnet-4.5": (3.00, 15.00),
    "google/gemini-2.5-pro": (1.25, 10.00),
    "google/gemini-2.5-flash": (0.30, 2.50),
    "meta-llama/llama-3.3-70b-instruct": (0.12, 0.30),
    "deepseek/deepseek-chat": (0.30, 0.90),
    "mistralai/mistral-large": (2.00, 6.00),
}

VARIANTS = {
    "pooled_wiki": ("pooled", ("wikipedia",)),
    "pooled_both": ("pooled", ("wikipedia", "openalex")),
    "stance_wiki": ("stance", ("wikipedia",)),
}


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=REPO, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def load_prompts(path: Path):
    data = json.loads(path.read_text(encoding="utf-8"))
    return data["system_prompt"], [PromptItem(p["id"], p["category"], p["text"]) for p in data["prompts"]]


def estimate(models, n_prompts: int, checker=(0.15, 0.60)) -> dict:
    """Rough upper estimate of spend. 400 output tokens per answer; ~6 claims per answer."""
    answers = n_prompts * len(models)
    responder_usd = sum(
        n_prompts * (150 * RESPONDERS.get(m, (3.0, 15.0))[0] + 400 * RESPONDERS.get(m, (3.0, 15.0))[1]) / 1e6
        for m in models
    )
    claims = answers * 6
    # per answer: extraction ~900 in/250 out; per claim: normalisation ~150/40 + pooled NLI ~2400/60
    checker_usd = (answers * (900 * checker[0] + 250 * checker[1])
                   + claims * ((150 + 2400) * checker[0] + (40 + 60) * checker[1])) / 1e6
    return {"answers": answers, "claims_upper": claims,
            "responders_usd": round(responder_usd, 2), "checker_usd": round(checker_usd, 2),
            "total_usd": round(responder_usd + checker_usd, 2)}


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="*", default=list(RESPONDERS))
    ap.add_argument("--variant", default="pooled_wiki", choices=sorted(VARIANTS))
    ap.add_argument("--prompts", default=str(REPO / "data" / "llm_eval" / "prompts.json"))
    ap.add_argument("--limit", type=int, default=None, help="Use only the first N prompts")
    ap.add_argument("--budget-usd", type=float, default=3.0)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--run-id", default=None)
    ap.add_argument("--dry-run", action="store_true", help="Print the plan and cost estimate, call nothing")
    args = ap.parse_args()

    system_prompt, prompts = load_prompts(Path(args.prompts))
    if args.limit:
        prompts = prompts[: args.limit]

    plan = estimate(args.models, len(prompts))
    print(f"{len(prompts)} prompts x {len(args.models)} models = {plan['answers']} answers")
    print(f"estimated spend: responders ${plan['responders_usd']}, checker ${plan['checker_usd']}, "
          f"total about ${plan['total_usd']} (upper bound)")
    if args.dry_run:
        for m in args.models:
            print("  -", m)
        return
    if plan["total_usd"] > args.budget_usd:
        print(f"warning: estimate exceeds --budget-usd {args.budget_usd}; the run stops when spend reaches it")

    mode, retrievers = VARIANTS[args.variant]
    settings = dataclasses.replace(Settings.from_env(), verdict_mode=mode, retrievers=retrievers, cache_enabled=False)
    pipeline = build_pipeline(settings)
    llm = pipeline.claim_service.llm_provider

    run_id = args.run_id or f"audit_{datetime.datetime.now():%Y%m%d_%H%M%S}"
    out_dir = REPO / "results" / "llm_eval" / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    def spent_usd() -> float:
        # Responder prices are looked up per model; the checker uses its own small-model rate.
        meter = CostMeter(read=lambda: {"prompt_tokens": llm.prompt_tokens, "completion_tokens": llm.completion_tokens},
                          usd_per_m_prompt=2.0, usd_per_m_completion=8.0)
        return meter.usd()  # deliberately pessimistic blended rate

    async def respond(model: str, p: PromptItem) -> str:
        return await llm.generate_text(p.text, model=model, system=system_prompt, max_tokens=400)

    async def extract(text: str):
        claims = await pipeline.claim_service.extract_claims(text)
        return [c.original_text for c in claims[: settings.max_claims]]

    async def check(text: str):
        a = await pipeline.assess_claim(ExtractedClaim(id="a", original_text=text, context=text))
        return {"verdict": a.verdict, "sources_considered": len(a.evidence), "sources_relevant": a.sources_relevant}

    responses = await collect_responses(
        args.models, prompts, respond, out_dir / "responses.jsonl", concurrency=args.concurrency
    )
    claims = await check_responses(
        responses, extract, check, out_dir / "claims.jsonl", concurrency=args.concurrency,
        budget_ok=lambda: spent_usd() < args.budget_usd,
    )

    summary = summarize(claims, responses)
    meta = {
        "run_id": run_id, "started": datetime.datetime.now().isoformat(timespec="seconds"),
        "prompts": len(prompts), "models": args.models, "variant": args.variant,
        "checker_model": settings.openrouter_model, "git_sha": git_sha(),
        "llm_calls": llm.calls, "prompt_tokens": llm.prompt_tokens, "completion_tokens": llm.completion_tokens,
    }
    pairs = {}
    models = [m for m in summary if summary[m]["claims_checked"]]
    for i, a in enumerate(models):
        for b in models[i + 1:]:
            pairs[f"{a} - {b}"] = bootstrap_difference([c for c in claims], a, b, "refuted")

    (out_dir / "summary.json").write_text(
        json.dumps({"meta": meta, "models": summary, "refuted_rate_differences": pairs}, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(render_markdown(summary, meta), encoding="utf-8")
    (out_dir / "table_models.tex").write_text(render_latex_table(summary) + "\n", encoding="utf-8")
    print((out_dir / "summary.md").read_text(encoding="utf-8"))
    print(f"written to {out_dir}")


if __name__ == "__main__":
    asyncio.run(main())
