import pytest

from app.models.schemas import ConstructionFamily, Evidence
from app.services.algo.stance import (
    AssessedSource, NullNLIAdapter, SourceStance, StanceList, StanceService, aggregate, quote_in_source,
)
from tests.mocks.providers import MockLLMProvider


def ev(i, text=None):
    return Evidence(id=f"e{i}", text=text or f"Source {i} says something about the topic in detail.",
                    construction_family=ConstructionFamily.ambiguous_claim)


def src(i, stance, conf=0.9, quote="says something about"):
    return AssessedSource(ev(i), stance, conf, quote if stance in ("supports", "refutes") else None)


# ---- aggregation rules ----

def test_no_sources():
    r = aggregate([])
    assert r.verdict == "no_sources" and r.support == 0 and r.conflict == 0


def test_two_supports_is_supported():
    r = aggregate([src(1, "supports", 0.6), src(2, "supports", 0.6), src(3, "irrelevant")])
    assert r.verdict == "supported"
    assert r.relevant == 2
    assert r.support == pytest.approx(1.0) and r.conflict == 0.0


def test_single_strong_support_is_enough_but_single_weak_is_not():
    assert aggregate([src(1, "supports", 0.8)]).verdict == "supported"
    weak = aggregate([src(1, "supports", 0.6), src(2, "neutral", 0.7)])
    assert weak.verdict == "insufficient"
    assert weak.leaning == "supports"


def test_below_confidence_floor_does_not_count():
    r = aggregate([src(1, "supports", 0.49), src(2, "supports", 0.3)])
    assert r.verdict == "insufficient" and r.leaning is None


def test_support_without_quote_does_not_count():
    s = AssessedSource(ev(1), "supports", 0.95, None)
    assert aggregate([s]).verdict == "insufficient"


def test_refuted():
    assert aggregate([src(1, "refutes", 0.9)]).verdict == "refuted"


def test_both_sides_present_is_mixed():
    r = aggregate([src(1, "supports", 0.9), src(2, "refutes", 0.6)])
    assert r.verdict == "mixed"
    assert 0 < r.support < 1 and 0 < r.conflict < 1


def test_both_sides_weak_stays_insufficient():
    r = aggregate([src(1, "supports", 0.55), src(2, "refutes", 0.55)])
    assert r.verdict == "insufficient" and r.leaning is None


def test_only_neutral_and_irrelevant_is_insufficient():
    r = aggregate([src(1, "neutral", 0.8), src(2, "irrelevant", 0.9)])
    assert r.verdict == "insufficient" and r.relevant == 1


def test_quote_matching_ignores_case_and_whitespace_and_rejects_short():
    assert quote_in_source("the  WATER boils", "Here the water\nboils at 100C.")
    assert not quote_in_source("boils", "boils")          # too short to be evidence
    assert not quote_in_source("water freezes at", "water boils at 100C")


# ---- service ----

def _service(stances):
    llm = MockLLMProvider()
    llm.set_response(StanceList, StanceList(stances=stances))
    return StanceService(llm), llm


@pytest.mark.asyncio
async def test_service_downgrades_unverifiable_quotes():
    sources = [ev(0, "Water boils at one hundred degrees Celsius at sea level."), ev(1, "Unrelated text about cats.")]
    service, llm = _service([
        SourceStance(index=0, stance="supports", confidence=0.95, quote="boils at one hundred degrees Celsius"),
        SourceStance(index=1, stance="refutes", confidence=0.99, quote="this quote is invented by the model"),
    ])

    result = await service.assess("Water boils at 100C.", sources)

    assert [s.stance for s in result.sources] == ["supports", "neutral"]
    assert result.verdict == "supported"
    assert "Water boils at 100C." in llm.call_history[0][0]
    assert 'index="1"' in llm.call_history[0][0]


@pytest.mark.asyncio
async def test_service_handles_missing_and_out_of_range_indices():
    service, _ = _service([SourceStance(index=0, stance="supports", confidence=0.9, quote="something about the topic"),
                           SourceStance(index=7, stance="refutes", confidence=0.9, quote="x" * 10)])
    result = await service.assess("claim", [ev(0), ev(1)])
    assert [s.stance for s in result.sources] == ["supports", "neutral"]   # index 1 skipped, 7 ignored
    assert result.sources[1].confidence == 0.0


@pytest.mark.asyncio
async def test_service_no_evidence_makes_no_llm_call():
    service, llm = _service([])
    result = await service.assess("claim", [])
    assert result.verdict == "no_sources" and llm.call_history == []


@pytest.mark.asyncio
async def test_null_nli_returns_zeros():
    assert await NullNLIAdapter().verify_entailment("c", ["e"]) == (0.0, 0.0)
