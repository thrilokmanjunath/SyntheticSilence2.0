import hashlib

import numpy as np
import pytest

from app.models.claim import ExtractedClaim
from app.models.schemas import ConstructionFamily, Evidence
from app.services.algo.density import DensityEstimator
from app.services.algo.engine import CoreResearchEngine
from app.services.algo.nli import LLMNLIAdapter, NLIPrediction
from app.services.algo.uncertainty import SimilarityDistributionEntropy
from app.services.analysis.calibration import ConformalCalibrator
from app.services.analysis.explanation import ExplanationOutput, ExplanationService
from app.services.analysis.temporal import TemporalAnalysisService
from app.services.claim_service import ClaimList, ClaimService, NormalizedResponse
from app.services.pipeline import ResearchPipeline
from app.services.ranking_service import EvidenceRankingService
from app.services.retrieval_service import RetrievalError
from tests.mocks.providers import MockLLMProvider, MockRetrievalProvider

DIM = 16


class FakeEmbedder:
    """Deterministic stand-in for the sentence-transformer so these tests stay fast."""

    def get_embeddings(self, texts):
        if not texts:
            return np.array([])
        rows = []
        for t in texts:
            seed = int(hashlib.sha256(t.encode()).hexdigest()[:8], 16)
            rows.append(np.random.default_rng(seed).normal(size=DIM))
        return np.array(rows)


def _claim(text: str, n: int = 0) -> ExtractedClaim:
    return ExtractedClaim(id=f"c{n}", original_text=text, context=text)


def _evidence(n: int, year: int | None = 2020) -> list[Evidence]:
    return [
        Evidence(
            id=f"https://openalex.org/W{i}",
            text=f"Study {i} on the topic.",
            source_url=f"https://doi.org/10.1/{i}",
            publication_year=year,
            construction_family=ConstructionFamily.ambiguous_claim,
        )
        for i in range(n)
    ]


def build(claims, evidence=None, nli=(0.8, 0.1), max_claims=6):
    llm = MockLLMProvider()
    llm.set_response(ClaimList, ClaimList(claims=claims))
    llm.set_response(
        NormalizedResponse, NormalizedResponse(normalized_text="n", core_entity="entity", core_predicate="pred")
    )
    llm.set_response(
        NLIPrediction,
        NLIPrediction(entailment_score=nli[0], contradiction_score=nli[1], neutral_score=0.1, explanation="x"),
    )
    llm.set_response(ExplanationOutput, ExplanationOutput(explanation="Because."))

    retrieval = MockRetrievalProvider()
    retrieval.set_returns(evidence or [])

    density = DensityEstimator(n_neighbors=3)
    density.fit(np.random.default_rng(0).normal(size=(40, DIM)))

    pipeline = ResearchPipeline(
        claim_service=ClaimService(llm),
        retrieval_service=retrieval,
        ranking_service=EvidenceRankingService(),
        core_engine=CoreResearchEngine(FakeEmbedder(), density, SimilarityDistributionEntropy(), LLMNLIAdapter(llm)),
        temporal_service=TemporalAnalysisService(cutoff_year=2023),
        calibrator=ConformalCalibrator(),
        explanation_service=ExplanationService(llm),
        max_claims=max_claims,
    )
    return pipeline, retrieval


@pytest.mark.asyncio
async def test_happy_path_attaches_evidence_and_stays_uncalibrated():
    pipeline, _ = build([_claim("Claim one.", 1), _claim("Claim two.", 2)], evidence=_evidence(3))

    run = await pipeline.run("text")

    assert [o.claim.original_text for o in run.outcomes] == ["Claim one.", "Claim two."]
    assert not run.truncated
    first = run.outcomes[0]
    assert len(first.evidence) == 3
    assert first.signal.evidence_coverage == 1.0
    assert first.signal.semantic_support == 0.8
    assert first.signal.calibration_status == "NOT_CALIBRATED"
    assert first.signal.insufficiency_signal is not None
    assert 0.0 <= first.signal.temporal_coverage <= 1.0
    assert first.explanation == "Because."


@pytest.mark.asyncio
async def test_no_evidence_is_missing_evidence_with_full_uncertainty():
    pipeline, _ = build([_claim("Obscure claim.", 1)], evidence=[])

    outcome = (await pipeline.run("text")).outcomes[0]

    assert outcome.evidence == []
    assert outcome.signal.evidence_coverage == 0.0
    assert outcome.signal.uncertainty == 1.0
    assert outcome.signal.construction_family_estimate == "missing_evidence"


@pytest.mark.asyncio
async def test_recent_sources_flag_temporal_novelty():
    pipeline, _ = build([_claim("New claim.", 1)], evidence=_evidence(2, year=2025))

    outcome = (await pipeline.run("text")).outcomes[0]

    assert outcome.signal.temporal_coverage == 1.0
    assert outcome.signal.construction_family_estimate == "temporal_novelty"


@pytest.mark.asyncio
async def test_high_contradiction_is_labelled_contradictory():
    pipeline, _ = build([_claim("Disputed.", 1)], evidence=_evidence(2), nli=(0.05, 0.9))

    outcome = (await pipeline.run("text")).outcomes[0]

    assert outcome.signal.construction_family_estimate == "contradictory"


@pytest.mark.asyncio
async def test_retrieval_outage_fails_the_run_instead_of_reporting_silence():
    pipeline, retrieval = build([_claim("Claim.", 1)])
    retrieval.should_fail = True

    with pytest.raises(Exception, match="Mock retrieval failure"):
        await pipeline.run("text")


@pytest.mark.asyncio
async def test_retrieval_error_type_propagates():
    pipeline, retrieval = build([_claim("Claim.", 1)])

    async def boom(*a, **k):
        raise RetrievalError("down")

    retrieval.retrieve_evidence = boom
    with pytest.raises(RetrievalError):
        await pipeline.run("text")


def build_stance(claims, evidence, stances):
    """Pipeline in stance mode: the engine's NLI is nulled and per-source stance decides the verdict."""
    from app.services.algo.stance import NullNLIAdapter, StanceList, StanceService

    pipeline, retrieval = build(claims, evidence=evidence)
    llm = pipeline.claim_service.llm_provider
    llm.set_response(StanceList, StanceList(stances=stances))
    pipeline.core.nli = NullNLIAdapter()
    pipeline.stance = StanceService(llm)
    return pipeline, llm


@pytest.mark.asyncio
async def test_stance_mode_sets_verdict_support_and_conflict_from_sources():
    from app.services.algo.stance import SourceStance

    evidence = [
        Evidence(id="a", text="Water boils at 100 degrees Celsius at sea level.",
                 construction_family=ConstructionFamily.ambiguous_claim),
        Evidence(id="b", text="Water boils at one hundred degrees under standard pressure.",
                 construction_family=ConstructionFamily.ambiguous_claim),
        Evidence(id="c", text="A page about ferrets.", construction_family=ConstructionFamily.ambiguous_claim),
    ]
    pipeline, llm = build_stance(
        [_claim("Water boils at 100C.", 1)], evidence,
        [SourceStance(index=0, stance="supports", confidence=0.9, quote="boils at 100 degrees"),
         SourceStance(index=1, stance="supports", confidence=0.7, quote="boils at one hundred degrees"),
         SourceStance(index=2, stance="irrelevant", confidence=0.9)],
    )

    outcome = (await pipeline.run("text")).outcomes[0]

    assert outcome.verdict == "supported"
    assert outcome.sources_relevant == 2
    assert outcome.signal.semantic_support == pytest.approx(1.0)
    assert outcome.signal.contradiction_level == 0.0
    assert [s.stance for s in outcome.assessed] == ["supports", "supports", "irrelevant"]
    # stance judges the claim exactly as written, never the lossy normalised form ("n" in this mock)
    stance_prompt = [p for p, schema in llm.call_history if schema.__name__ == "StanceList"][0]
    assert "<text>Water boils at 100C.</text>" in stance_prompt
    # the explanation prompt is told the decided verdict, so the text cannot contradict it
    explanation_prompt = [p for p, schema in llm.call_history if schema is ExplanationOutput][0]
    assert "verdict=supported" in explanation_prompt


@pytest.mark.asyncio
async def test_pooled_mode_uses_engine_nli_for_verdict():
    pipeline, _ = build([_claim("Claim.", 1)], evidence=_evidence(2), nli=(0.9, 0.05))
    outcome = (await pipeline.run("text")).outcomes[0]
    assert outcome.verdict == "supported" and outcome.assessed is None


class CountingRetrieval:
    name = "counting"

    def __init__(self, evidence):
        self.evidence, self.calls, self.fail = evidence, 0, False

    async def retrieve_evidence(self, claim, max_results=10):
        self.calls += 1
        if self.fail:
            raise RetrievalError("down")
        return self.evidence


def _cached(pipeline, retrieval, evidence=None, **extra):
    from app.services.cache import ResultCache

    retrieval.evidence = evidence if evidence is not None else retrieval.evidence
    pipeline.retrieval = retrieval
    pipeline.cache = ResultCache(":memory:")
    pipeline.cache_fingerprint = {"mode": "pooled", **extra}
    return pipeline


@pytest.mark.asyncio
async def test_repeat_claim_is_served_from_cache_without_new_work():
    pipeline, _ = build([_claim("Cached claim.", 1)], evidence=_evidence(2))
    retrieval = CountingRetrieval(_evidence(2))
    _cached(pipeline, retrieval)
    llm = pipeline.claim_service.llm_provider

    first = (await pipeline.run("text")).outcomes[0]
    calls_after_first = len(llm.call_history)
    second = (await pipeline.run("text")).outcomes[0]

    assert retrieval.calls == 1                       # no second search
    assert len(llm.call_history) == calls_after_first + 1   # only claim extraction re-ran
    assert second.verdict == first.verdict
    assert second.explanation == first.explanation
    assert [e.id for e in second.evidence] == [e.id for e in first.evidence]
    assert second.signal.model_dump() == first.signal.model_dump()


@pytest.mark.asyncio
async def test_failures_are_never_cached():
    pipeline, _ = build([_claim("Flaky claim.", 1)])
    retrieval = CountingRetrieval(_evidence(1))
    retrieval.fail = True
    _cached(pipeline, retrieval)

    with pytest.raises(RetrievalError):
        await pipeline.run("text")
    assert len(pipeline.cache) == 0

    retrieval.fail = False
    outcome = (await pipeline.run("text")).outcomes[0]
    assert outcome.verdict in ("supported", "insufficient", "refuted")
    assert retrieval.calls == 2 and len(pipeline.cache) == 1


@pytest.mark.asyncio
async def test_config_change_does_not_reuse_a_cached_result():
    pipeline, _ = build([_claim("Same claim.", 1)], evidence=_evidence(1))
    retrieval = CountingRetrieval(_evidence(1))
    _cached(pipeline, retrieval, model="a")
    await pipeline.run("text")
    pipeline.cache_fingerprint = {"mode": "pooled", "model": "b"}
    await pipeline.run("text")
    assert retrieval.calls == 2


@pytest.mark.asyncio
async def test_stance_mode_result_roundtrips_through_the_cache():
    from app.services.algo.stance import SourceStance

    evidence = [Evidence(id="a", text="Water boils at 100 degrees Celsius at sea level.",
                         construction_family=ConstructionFamily.ambiguous_claim)]
    pipeline, _ = build_stance(
        [_claim("Water boils at 100C.", 1)], evidence,
        [SourceStance(index=0, stance="supports", confidence=0.95, quote="boils at 100 degrees Celsius")],
    )
    retrieval = CountingRetrieval(evidence)
    _cached(pipeline, retrieval, mode="stance")

    first = (await pipeline.run("text")).outcomes[0]
    second = (await pipeline.run("text")).outcomes[0]

    assert retrieval.calls == 1
    assert second.assessed is not None and second.assessed[0].stance == "supports"
    assert second.assessed[0].quote == first.assessed[0].quote
    assert second.assessed[0].evidence is second.evidence[0]   # identity preserved for API alignment


@pytest.mark.asyncio
async def test_stream_announces_claims_first_then_each_result():
    from app.services.pipeline import ClaimEvent, ClaimsEvent

    pipeline, _ = build([_claim("One.", 1), _claim("Two.", 2), _claim("Three.", 3)], evidence=_evidence(2))

    events = [e async for e in pipeline.run_stream("text")]

    assert isinstance(events[0], ClaimsEvent)
    assert [c.original_text for c in events[0].claims] == ["One.", "Two.", "Three."]
    results = [e for e in events[1:] if isinstance(e, ClaimEvent)]
    assert sorted(e.index for e in results) == [0, 1, 2]
    assert len(events) == 4


@pytest.mark.asyncio
async def test_stream_isolates_a_failing_claim():
    from app.services.pipeline import ClaimErrorEvent, ClaimEvent

    pipeline, retrieval = build([_claim("Good.", 1), _claim("Bad.", 2)], evidence=_evidence(2))
    calls = {"n": 0}
    original = retrieval.retrieve_evidence

    async def flaky(claim, max_results=10):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RetrievalError("search down")
        return await original(claim, max_results)

    retrieval.retrieve_evidence = flaky

    events = [e async for e in pipeline.run_stream("text")][1:]

    errors = [e for e in events if isinstance(e, ClaimErrorEvent)]
    done = [e for e in events if isinstance(e, ClaimEvent)]
    assert len(errors) == 1 and len(done) == 1
    assert isinstance(errors[0].error, RetrievalError)
    assert errors[0].index != done[0].index


@pytest.mark.asyncio
async def test_stream_with_no_claims_emits_only_the_claims_event():
    pipeline, _ = build([], evidence=_evidence(1))
    events = [e async for e in pipeline.run_stream("text")]
    assert len(events) == 1 and events[0].claims == []


@pytest.mark.asyncio
async def test_closing_the_stream_early_cancels_remaining_work():
    import asyncio

    pipeline, retrieval = build([_claim("A.", 1), _claim("B.", 2), _claim("C.", 3)], evidence=_evidence(1))
    started = []

    async def slow(claim, max_results=10):
        started.append(1)
        await asyncio.sleep(30)
        return []

    retrieval.retrieve_evidence = slow
    agen = pipeline.run_stream("text")
    await agen.__anext__()          # the claims event; workers are created on the next pull
    pull = asyncio.create_task(agen.__anext__())
    await asyncio.sleep(0.1)        # workers are now blocked inside slow()
    assert len(started) == 3
    pull.cancel()                   # what a client disconnect does to the response body
    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(pull, timeout=2)   # must not wait for the 30 s sleeps
    await asyncio.sleep(0)
    leftover = [t for t in asyncio.all_tasks() if t is not asyncio.current_task() and not t.done()]
    assert leftover == []


@pytest.mark.asyncio
async def test_claim_cap_sets_truncated():
    claims = [_claim(f"Claim {i}.", i) for i in range(1, 9)]
    pipeline, _ = build(claims, evidence=_evidence(1), max_claims=6)

    run = await pipeline.run("text")

    assert len(run.outcomes) == 6
    assert run.truncated


@pytest.mark.asyncio
async def test_claim_service_dedupes_and_reassigns_ids():
    llm = MockLLMProvider()
    llm.set_response(
        ClaimList,
        ClaimList(
            claims=[
                ExtractedClaim(id="x", original_text="Same claim.", context="ctx"),
                ExtractedClaim(id="x", original_text="same claim.", context=""),
                ExtractedClaim(id="x", original_text="   ", context=""),
                ExtractedClaim(id="x", original_text="Other claim.", context=""),
            ]
        ),
    )

    claims = await ClaimService(llm).extract_claims("text")

    assert [c.id for c in claims] == ["c1", "c2"]
    assert [c.original_text for c in claims] == ["Same claim.", "Other claim."]
    assert claims[1].context == "Other claim."
