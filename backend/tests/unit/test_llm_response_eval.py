import json

import pytest

from experiments.llm_response_eval import (
    ClaimRecord, PromptItem, ResponseRecord, bootstrap_difference, check_responses, collect_responses,
    render_latex_table, render_markdown, summarize, summarize_model, wilson_interval,
)


def claim(model, prompt, verdict, cat="science", sources=3, relevant=2, text="c"):
    return ClaimRecord(model, prompt, cat, text, verdict, sources, relevant)


def resp(model, prompt, cat="science", error=None):
    return ResponseRecord(model, prompt, cat, "answer" if error is None else "", error)


def test_wilson_matches_known_values():
    lo, hi = wilson_interval(50, 100)
    assert lo == pytest.approx(0.4038, abs=1e-3) and hi == pytest.approx(0.5962, abs=1e-3)
    assert wilson_interval(0, 0) == (0.0, 0.0)
    assert wilson_interval(0, 10)[0] == 0.0 and wilson_interval(10, 10)[1] == 1.0


def test_summary_counts_rates_and_response_level_refuted_share():
    claims = [
        claim("m", "p1", "supported"), claim("m", "p1", "supported"), claim("m", "p1", "refuted"),
        claim("m", "p2", "supported"), claim("m", "p2", "no_sources", sources=0, relevant=0),
        claim("m", "p3", "insufficient"),
        claim("m", "p4", "error"),                                   # failed check: excluded from rates
    ]
    s = summarize_model(claims, [resp("m", f"p{i}") for i in (1, 2, 3, 4)])

    assert s["claims_checked"] == 6 and s["claims_failed"] == 1
    assert s["responses_scored"] == 3                                # p4 had no successfully checked claim
    assert s["claims_per_response"] == pytest.approx(2.0)
    rates = s["claim_rates"]
    assert rates["supported"]["n"] == 3 and rates["supported"]["of"] == 6
    assert rates["refuted"]["rate"] == pytest.approx(1 / 6)
    assert s["responses_with_refuted"]["n"] == 1 and s["responses_with_refuted"]["of"] == 3
    assert s["support_among_decisive"]["rate"] == pytest.approx(3 / 4)
    assert s["mean_sources"] == pytest.approx((3 * 5 + 0) / 6)       # five claims with 3 sources, one with 0
    assert s["by_category"]["science"] == {"claims": 6, "supported": 3, "refuted": 1}


def test_failed_responses_are_counted_not_scored():
    s = summarize_model([], [resp("m", "p1"), resp("m", "p2", error="402")])
    assert s["responses"] == 2 and s["responses_failed"] == 1 and s["claims_checked"] == 0
    assert s["claims_per_response"] is None
    assert s["claim_rates"]["supported"]["rate"] is None


def test_summarize_groups_by_model_sorted():
    out = summarize([claim("b", "p", "supported"), claim("a", "p", "refuted")], [resp("a", "p"), resp("b", "p")])
    assert list(out) == ["a", "b"]


def test_bootstrap_detects_a_clear_difference_and_is_deterministic():
    claims = []
    for i in range(30):
        claims.append(claim("good", f"p{i}", "supported"))
        claims.append(claim("bad", f"p{i}", "refuted" if i % 2 == 0 else "supported"))
    d1 = bootstrap_difference(claims, "bad", "good", "refuted", iterations=500, seed=1)
    d2 = bootstrap_difference(claims, "bad", "good", "refuted", iterations=500, seed=1)

    assert d1 == d2
    assert d1["prompts"] == 30
    assert d1["diff"] == pytest.approx(0.5)
    assert d1["ci95"][0] > 0.2                                         # interval excludes zero


def test_bootstrap_uses_only_shared_prompts_and_handles_no_overlap():
    claims = [claim("a", "p1", "refuted"), claim("b", "p2", "supported")]
    assert bootstrap_difference(claims, "a", "b")["prompts"] == 0
    claims.append(claim("b", "p1", "supported"))
    assert bootstrap_difference(claims, "a", "b", iterations=50)["prompts"] == 1


def test_renderers_include_every_model():
    summary = summarize(
        [claim("openai/gpt-4o", "p", "supported"), claim("google/gemini_x", "p", "refuted")],
        [resp("openai/gpt-4o", "p"), resp("google/gemini_x", "p")],
    )
    md = render_markdown(summary, {"prompts": 1, "checker_model": "c", "variant": "v", "run_id": "r", "started": "now"})
    assert "openai/gpt-4o" in md and "google/gemini_x" in md and "not ground truth" in md
    tex = render_latex_table(summary)
    assert tex.count("\\\\") == 2 and "gemini\\_x" in tex


@pytest.mark.asyncio
async def test_collect_is_resumable_and_records_failures(tmp_path):
    prompts = [PromptItem("p1", "science", "q1"), PromptItem("p2", "history", "q2")]
    calls = []
    fail = {"on": True}

    async def respond(model, p):
        calls.append((model, p.id))
        if model == "flaky" and fail["on"]:
            raise RuntimeError("402 no credit")
        return f"{model} answers {p.id}"

    path = tmp_path / "responses.jsonl"
    first = await collect_responses(["good", "flaky"], prompts, respond, path, log=lambda s: None)
    assert sum(1 for r in first if r.error is None) == 2 and sum(1 for r in first if r.error) == 2

    calls.clear()
    fail["on"] = False
    second = await collect_responses(["good", "flaky"], prompts, respond, path, log=lambda s: None)
    assert sorted(calls) == [("flaky", "p1"), ("flaky", "p2")]          # only the failures were re-asked
    assert all(r.error is None for r in second) and len(second) == 4


@pytest.mark.asyncio
async def test_check_splits_claims_isolates_failures_and_resumes(tmp_path):
    responses = [resp("m", "p1"), resp("m", "p2"), resp("m", "p3", error="boom")]
    extracted = {"answer": ["Claim one is true.", "Claim two is false.", "Claim three breaks."]}
    state = {"fail_three": True, "checks": 0}

    async def extract(text):
        return extracted["answer"]

    async def check(text):
        state["checks"] += 1
        if "breaks" in text and state["fail_three"]:
            raise RuntimeError("retrieval down")
        verdict = "supported" if "true" in text else "refuted" if "false" in text else "insufficient"
        return {"verdict": verdict, "sources_considered": 4, "sources_relevant": 3}

    path = tmp_path / "claims.jsonl"
    first = await check_responses(responses, extract, check, path, log=lambda s: None)

    assert len(first) == 6                                              # failed response p3 is skipped
    assert sum(1 for c in first if c.verdict == "error") == 2
    assert {c.verdict for c in first if c.prompt_id == "p1"} == {"supported", "refuted", "error"}

    state["fail_three"], state["checks"] = False, 0
    second = await check_responses(responses, extract, check, path, log=lambda s: None)
    assert state["checks"] == 6                                         # both answers had an error, so both are redone
    assert not any(c.verdict == "error" for c in second) and len(second) == 6

    state["checks"] = 0
    await check_responses(responses, extract, check, path, log=lambda s: None)
    assert state["checks"] == 0                                         # fully resumed: nothing re-run


@pytest.mark.asyncio
async def test_check_stops_at_budget_and_reports_incomplete(tmp_path):
    responses = [resp("m", f"p{i}") for i in range(5)]
    done = {"n": 0}

    async def extract(text):
        return ["one claim here"]

    async def check(text):
        done["n"] += 1
        return {"verdict": "supported"}

    out = await check_responses(responses, extract, check, tmp_path / "c.jsonl", concurrency=1,
                                budget_ok=lambda: done["n"] < 2, log=lambda s: None)
    assert 1 <= len(out) < 5


def test_prompt_file_is_well_formed():
    from pathlib import Path

    data = json.loads((Path(__file__).resolve().parents[3] / "data" / "llm_eval" / "prompts.json").read_text("utf-8"))
    ids = [p["id"] for p in data["prompts"]]
    assert len(ids) == len(set(ids)) == 40
    assert {p["category"] for p in data["prompts"]} == {"science", "history", "geography", "medicine", "technology", "misconception"}
    assert all(len(p["text"].strip()) > 15 for p in data["prompts"])
    assert data["system_prompt"].strip()
