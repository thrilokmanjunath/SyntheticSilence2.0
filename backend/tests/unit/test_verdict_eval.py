import json
from pathlib import Path

import pytest

from app.services.verdict import VERDICT_TO_FEVER, pooled_verdict
from experiments.verdict_eval import (
    EvalClaim, Prediction, RunConfig, compute_metrics, run_eval, sample_fever, wilson_interval,
)


def _write_fever(path: Path, per_label: int = 20, dup: int = 2) -> None:
    rows = []
    i = 0
    for label in ("SUPPORTS", "REFUTES", "NOT ENOUGH INFO"):
        for _ in range(per_label):
            i += 1
            for _ in range(dup):  # paper_dev repeats claims once per evidence annotation
                rows.append({"id": i, "label": label, "claim": f"claim {i}"})
    rows.append({"id": 9999, "label": "SUPPORTS", "claim": "   "})  # empty claim dropped
    path.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")


def _pred(gold, predicted, relevant=1, latency=1.0):
    verdict = {"SUPPORTS": "supported", "REFUTES": "refuted", "NOT ENOUGH INFO": "insufficient", "MIXED": "mixed", "ERROR": "error"}[predicted]
    return Prediction(id="x", text="t", gold=gold, verdict=verdict, predicted=predicted,
                      sources_considered=relevant, sources_relevant=relevant, latency_s=latency)


def test_pooled_verdict_bins():
    assert pooled_verdict(0.9, 0.0, 0) == "no_sources"
    assert pooled_verdict(0.9, 0.6, 3) == "refuted"       # conflict checked first
    assert pooled_verdict(0.6, 0.1, 3) == "supported"
    assert pooled_verdict(0.59, 0.49, 3) == "insufficient"


def test_verdict_label_mapping_is_complete():
    assert set(VERDICT_TO_FEVER) == {"supported", "refuted", "mixed", "insufficient", "no_sources"}


def test_sample_is_balanced_deduped_and_deterministic(tmp_path):
    path = tmp_path / "dev.jsonl"
    _write_fever(path)
    a = sample_fever(path, 30, seed=7)
    b = sample_fever(path, 30, seed=7)
    assert [c.id for c in a] == [c.id for c in b]
    assert len({c.id for c in a}) == 30
    assert {l: sum(c.gold == l for c in a) for l in ("SUPPORTS", "REFUTES", "NOT ENOUGH INFO")} == {
        "SUPPORTS": 10, "REFUTES": 10, "NOT ENOUGH INFO": 10}
    assert [c.id for c in sample_fever(path, 30, seed=8)] != [c.id for c in a]


def test_sample_rejects_too_small_pool(tmp_path):
    path = tmp_path / "dev.jsonl"
    _write_fever(path, per_label=2)
    with pytest.raises(ValueError):
        sample_fever(path, 30)


def test_wilson_interval_bounds():
    lo, hi = wilson_interval(50, 100)
    assert 0.40 < lo < 0.5 < hi < 0.60
    assert wilson_interval(0, 0) == (0.0, 0.0)
    lo, hi = wilson_interval(10, 10)
    assert hi == 1.0 and lo > 0.6


def test_metrics_known_confusion():
    preds = (
        [_pred("SUPPORTS", "SUPPORTS")] * 6 + [_pred("SUPPORTS", "NOT ENOUGH INFO")] * 2 + [_pred("SUPPORTS", "REFUTES")] * 2
        + [_pred("REFUTES", "REFUTES")] * 5 + [_pred("REFUTES", "MIXED")] * 5
        + [_pred("NOT ENOUGH INFO", "NOT ENOUGH INFO", relevant=0)] * 8 + [_pred("NOT ENOUGH INFO", "SUPPORTS")] * 2
        + [_pred("SUPPORTS", "ERROR")]
    )
    m = compute_metrics(preds)

    assert m["n_total"] == 31 and m["n_scored"] == 30 and m["n_errors"] == 1
    assert m["confusion"]["SUPPORTS"]["SUPPORTS"] == 6
    assert m["accuracy"] == pytest.approx(19 / 30)
    sup = m["per_class"]["SUPPORTS"]
    assert sup["precision"] == pytest.approx(6 / 8)   # 6 right out of 8 predicted SUPPORTS
    assert sup["recall"] == pytest.approx(6 / 10)
    assert m["per_class"]["REFUTES"]["recall"] == pytest.approx(5 / 10)
    assert m["mixed_rate"] == pytest.approx(5 / 30)
    assert m["decisive_accuracy"] == pytest.approx(11 / 20)
    assert m["coverage"] == pytest.approx(22 / 30)    # 8 NEI rows had no relevant sources


@pytest.mark.asyncio
async def test_runner_resumes_records_errors_and_honours_budget(tmp_path):
    claims = [EvalClaim(id=str(i), text=f"c{i}", gold="SUPPORTS") for i in range(6)]
    calls = []

    async def assess(claim):
        calls.append(claim.id)
        if claim.id == "3":
            raise RuntimeError("boom")
        return {"verdict": "supported", "sources_considered": 2, "sources_relevant": 2, "support": 0.9, "conflict": 0.0}

    cfg = RunConfig(variant="t", n=6, seed=1, model="m", concurrency=1, budget_usd=1.0)
    out = tmp_path / "run"
    first = await run_eval(claims, assess, cfg, out, log=lambda s: None)
    assert first["metrics"]["n_errors"] == 1 and first["metrics"]["n_scored"] == 5
    assert (out / "report.md").exists()

    calls.clear()
    second = await run_eval(claims, assess, cfg, out, log=lambda s: None)
    assert calls == []   # nothing re-run, including the recorded error
    assert second["metrics"]["n_total"] == 6


@pytest.mark.asyncio
async def test_budget_stops_run_and_flags_incomplete(tmp_path):
    from experiments.verdict_eval import CostMeter

    claims = [EvalClaim(id=str(i), text=f"c{i}", gold="SUPPORTS") for i in range(5)]
    spent = {"p": 0}

    async def assess(claim):
        spent["p"] += 1_000_000   # $0.15 per claim at default pricing
        return {"verdict": "supported", "sources_considered": 1, "sources_relevant": 1}

    meter = CostMeter(read=lambda: {"prompt_tokens": spent["p"], "completion_tokens": 0})
    cfg = RunConfig(variant="t", n=5, seed=1, model="m", concurrency=1, budget_usd=0.30)
    result = await run_eval(claims, assess, cfg, tmp_path / "r", cost=meter, log=lambda s: None)

    assert result["budget_stopped"] and result["incomplete"]
    assert result["metrics"]["n_total"] < 5
