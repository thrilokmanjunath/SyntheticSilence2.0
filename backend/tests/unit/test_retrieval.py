import httpx
import numpy as np
import pytest

from app.models.claim import NormalizedClaim
from app.models.schemas import ConstructionFamily, Evidence
from app.services.ranking_service import EvidenceRankingService
from app.services.retrieval_service import (
    CompositeRetrievalService, OpenAlexRetrievalService, RetrievalBudgetError, RetrievalError,
)
from app.services.wikipedia_service import WikipediaRetrievalService

CLAIM = NormalizedClaim(id="n", extracted_claim_id="c", normalized_text="Honey does not spoil.",
                        core_entity="Honey", core_predicate="does not spoil")


def _client(handler, base="https://example.test"):
    return httpx.AsyncClient(base_url=base, transport=httpx.MockTransport(handler))


def _ev(i, text=None, kind="scholarly"):
    return Evidence(id=f"id{i}", text=text or f"text {i}", construction_family=ConstructionFamily.ambiguous_claim, kind=kind)


# ---- OpenAlex ----

@pytest.mark.asyncio
async def test_openalex_maps_works_and_year():
    def handler(request):
        assert request.headers["authorization"] == "Bearer KEY"
        return httpx.Response(200, json={"results": [
            {"id": "W1", "title": "Honey study", "abstract_inverted_index": {"Honey": [0], "keeps": [1]},
             "doi": "https://doi.org/10.1/x", "publication_year": 2019},
            {"id": "W2", "title": None, "abstract_inverted_index": None},   # nothing usable
        ]})

    svc = OpenAlexRetrievalService(api_key="KEY", client=_client(handler))
    out = await svc.retrieve_evidence(CLAIM)

    assert len(out) == 1
    assert out[0].text == "Honey keeps" and out[0].publication_year == 2019 and out[0].kind == "scholarly"


@pytest.mark.asyncio
async def test_openalex_spent_budget_raises_budget_error_and_stops_calling():
    calls = []

    def handler(request):
        calls.append(1)
        return httpx.Response(429, headers={"retry-after": "36000"}, json={"error": "budget"})

    svc = OpenAlexRetrievalService(client=_client(handler))
    with pytest.raises(RetrievalBudgetError, match="OPENALEX_API_KEY"):
        await svc.retrieve_evidence(CLAIM)
    with pytest.raises(RetrievalBudgetError):
        await svc.retrieve_evidence(CLAIM)
    assert len(calls) == 1   # second call short-circuits without a request


@pytest.mark.asyncio
async def test_openalex_short_429_is_retried_once():
    statuses = iter([429, 200])

    def handler(request):
        if next(statuses) == 429:
            return httpx.Response(429, headers={"retry-after": "0"})
        return httpx.Response(200, json={"results": []})

    svc = OpenAlexRetrievalService(client=_client(handler))
    assert await svc.retrieve_evidence(CLAIM) == []


@pytest.mark.asyncio
async def test_openalex_server_error_is_retrieval_error_not_empty():
    svc = OpenAlexRetrievalService(client=_client(lambda r: httpx.Response(500)))
    with pytest.raises(RetrievalError):
        await svc.retrieve_evidence(CLAIM)


# ---- Wikipedia ----

@pytest.mark.asyncio
async def test_wikipedia_merges_queries_skips_stubs_and_keeps_best_rank():
    seen = []

    def handler(request):
        q = request.url.params["gsrsearch"]
        seen.append(q)
        pages = {
            "Honey does not spoil.": [
                {"pageid": 1, "title": "Honey", "index": 2, "extract": "Honey is a sweet substance."},
                {"pageid": 9, "title": "Honey (disambiguation)", "index": 1, "extract": "Honey may refer to:"},
            ],
            "Honey": [
                {"pageid": 1, "title": "Honey", "index": 1, "extract": "Honey is a sweet substance."},
                {"pageid": 3, "title": "Beekeeping", "index": 2, "extract": "Beekeeping is the keeping of bees."},
            ],
        }[q]
        return httpx.Response(200, json={"query": {"pages": pages}})

    svc = WikipediaRetrievalService(client=httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    out = await svc.retrieve_evidence(CLAIM)

    assert sorted(seen) == ["Honey", "Honey does not spoil."]
    assert [e.title for e in out] == ["Honey", "Beekeeping"]
    assert all(e.kind == "encyclopedia" and e.publication_year is None for e in out)
    assert out[0].source_url == "https://en.wikipedia.org/?curid=1"


@pytest.mark.asyncio
async def test_wikipedia_no_pages_is_empty_not_error():
    svc = WikipediaRetrievalService(
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"batchcomplete": True})))
    )
    assert await svc.retrieve_evidence(CLAIM) == []


@pytest.mark.asyncio
async def test_wikipedia_http_failure_is_an_error():
    svc = WikipediaRetrievalService(
        client=httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(503)))
    )
    with pytest.raises(RetrievalError):
        await svc.retrieve_evidence(CLAIM)


# ---- composite ----

class Fake:
    def __init__(self, name, result=None, error=None):
        self.name, self._r, self._e = name, result, error

    async def retrieve_evidence(self, claim, max_results=10):
        if self._e:
            raise self._e
        return self._r


@pytest.mark.asyncio
async def test_composite_merges_and_dedupes_by_id_and_text():
    a = Fake("a", [_ev(1), _ev(2, "same body")])
    b = Fake("b", [_ev(1), _ev(3, "same body")])
    out = await CompositeRetrievalService([a, b]).retrieve_evidence(CLAIM)
    assert [e.id for e in out] == ["id1", "id2"]


@pytest.mark.asyncio
async def test_composite_tolerates_partial_failure_when_something_was_found():
    out = await CompositeRetrievalService(
        [Fake("a", error=RetrievalError("down")), Fake("b", [_ev(1)])]
    ).retrieve_evidence(CLAIM)
    assert len(out) == 1


@pytest.mark.asyncio
async def test_composite_failure_plus_empty_is_an_error_not_silence():
    with pytest.raises(RetrievalBudgetError):
        await CompositeRetrievalService(
            [Fake("a", error=RetrievalBudgetError("spent")), Fake("b", [])]
        ).retrieve_evidence(CLAIM)


@pytest.mark.asyncio
async def test_composite_all_empty_is_a_valid_empty_result():
    assert await CompositeRetrievalService([Fake("a", []), Fake("b", [])]).retrieve_evidence(CLAIM) == []


# ---- ranking ----

class KeywordEmbedder:
    """2-d toy space: axis 0 = 'honey', axis 1 = 'other'."""
    def get_embeddings(self, texts):
        return np.array([[1.0, 0.0] if "honey" in t.lower() else [0.0, 1.0] for t in texts])


@pytest.mark.asyncio
async def test_ranking_orders_by_similarity_caps_and_keeps_minimum():
    items = [_ev(1, "cats"), _ev(2, "honey keeps"), _ev(3, "dogs"), _ev(4, "honey and bees"), _ev(5, "rocks")]
    svc = EvidenceRankingService(embedder=KeywordEmbedder(), top_k=3, similarity_floor=0.5, min_keep=1)

    out = await svc.filter_and_rank(items, "honey claim")

    # two honey sources first; below-floor sources beyond min_keep are dropped
    assert [e.id for e in out] == ["id2", "id4"]
    assert out[0].relevance == pytest.approx(1.0)


@pytest.mark.asyncio
async def test_ranking_never_empties_a_nonempty_list():
    items = [_ev(1, "cats"), _ev(2, "dogs"), _ev(3, "rocks")]
    svc = EvidenceRankingService(embedder=KeywordEmbedder(), top_k=5, similarity_floor=0.9, min_keep=2)
    out = await svc.filter_and_rank(items, "honey claim")
    assert len(out) == 2


@pytest.mark.asyncio
async def test_ranking_without_embedder_or_claim_is_passthrough():
    items = [_ev(1), _ev(2)]
    assert await EvidenceRankingService().filter_and_rank(items, "claim") == items
    assert await EvidenceRankingService(embedder=KeywordEmbedder()).filter_and_rank(items) == items
