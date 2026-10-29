import json

import pytest
from fastapi.testclient import TestClient

from app import container
from app.api import routes
from app.config import ConfigurationError
from app.main import app
from app.models.claim import ExtractedClaim
from app.models.schemas import ConstructionFamily, Evidence, InsufficiencySignal
from app.services.algo.stance import AssessedSource
from app.services.pipeline import ClaimErrorEvent, ClaimEvent, ClaimOutcome, ClaimsEvent, PipelineRun
from app.services.providers.openrouter import LLMProviderError
from app.services.retrieval_service import RetrievalBudgetError, RetrievalError


class FakePipeline:
    def __init__(self, run=None, error=None):
        self._run, self._error = run, error

    async def run(self, text):
        if self._error:
            raise self._error
        return self._run


def _outcome():
    return ClaimOutcome(
        verdict="supported",
        sources_relevant=1,
        claim=ExtractedClaim(id="c1", original_text="Honey never spoils.", context="Honey never spoils."),
        signal=InsufficiencySignal(
            evidence_coverage=1.0,
            semantic_support=0.7,
            contradiction_level=0.1,
            retrieval_confidence=0.4,
            representation_density=0.6,
            uncertainty=0.5,
            temporal_coverage=0.0,
            insufficiency_signal=0.55,
            construction_family_estimate="ambiguous_claim",
        ),
        explanation="Sources agree.",
        evidence=[
            Evidence(
                id="W1",
                text="Archaeologists found edible honey.",
                source_url="https://doi.org/10.1/1",
                publication_year=2019,
                construction_family=ConstructionFamily.ambiguous_claim,
            )
        ],
    )


@pytest.fixture
def client():
    yield TestClient(app)
    app.dependency_overrides.clear()


def use(pipeline):
    app.dependency_overrides[routes.get_pipeline] = lambda: pipeline


def test_analyze_response_shape_matches_extension_contract(client):
    use(FakePipeline(run=PipelineRun(outcomes=[_outcome()], truncated=True)))

    res = client.post("/api/v1/analyze", json={"source_text": "Honey never spoils."})

    assert res.status_code == 200
    body = res.json()
    assert body["truncated"] is True
    item = body["results"][0]
    assert item["claim"]["original_text"] == "Honey never spoils."
    assert item["signal"]["semantic_support"] == 0.7
    assert item["signal"]["calibration_status"] == "NOT_CALIBRATED"
    assert item["explanation"] == "Sources agree."
    assert item["evidence"] == [
        {
            "id": "W1",
            "text": "Archaeologists found edible honey.",
            "title": None,
            "source_url": "https://doi.org/10.1/1",
            "publication_year": 2019,
            "kind": "scholarly",
            "stance": None,
            "confidence": None,
            "quote": None,
            "relevance": None,
        }
    ]
    assert item["verdict"] == "supported"
    assert item["sources_considered"] == 1 and item["sources_relevant"] == 1


def test_stance_fields_are_aligned_to_each_source(client):
    outcome = _outcome()
    second = Evidence(id="W2", text="A second source.", construction_family=ConstructionFamily.ambiguous_claim,
                      kind="encyclopedia", title="Honey", relevance=0.7)
    outcome.evidence.append(second)
    outcome.assessed = [
        AssessedSource(outcome.evidence[0], "supports", 0.9, "edible honey"),
        AssessedSource(second, "neutral", 0.4, None),
    ]
    outcome.verdict, outcome.sources_relevant = "insufficient", 2
    outcome.leaning = "supports"
    use(FakePipeline(run=PipelineRun(outcomes=[outcome])))

    item = client.post("/api/v1/analyze", json={"source_text": "x"}).json()["results"][0]

    assert [(e["stance"], e["confidence"], e["quote"]) for e in item["evidence"]] == [
        ("supports", 0.9, "edible honey"), ("neutral", 0.4, None)]
    assert item["evidence"][1]["kind"] == "encyclopedia" and item["evidence"][1]["relevance"] == 0.7
    assert item["verdict"] == "insufficient" and item["leaning"] == "supports"


class StreamingFake:
    def __init__(self, events=(), fail_with=None):
        self._events, self._fail = list(events), fail_with

    async def run_stream(self, text):
        for e in self._events:
            yield e
        if self._fail:
            raise self._fail


def _ndjson(res):
    return [json.loads(line) for line in res.text.splitlines() if line.strip()]


def test_stream_emits_claims_results_errors_and_done(client):
    claim = ExtractedClaim(id="c1", original_text="Honey never spoils.", context="Honey never spoils.")
    use(StreamingFake([
        ClaimsEvent(claims=[claim, claim], truncated=False),
        ClaimEvent(index=1, outcome=_outcome()),
        ClaimErrorEvent(index=0, error=RetrievalBudgetError("OpenAlex search budget is used up.")),
    ]))

    res = client.post("/api/v1/analyze/stream", json={"source_text": "x"})

    assert res.status_code == 200
    assert res.headers["content-type"].startswith("application/x-ndjson")
    lines = _ndjson(res)
    assert [l["type"] for l in lines] == ["claims", "claim", "claim_error", "done"]
    assert lines[0]["claims"][0]["original_text"] == "Honey never spoils."
    assert lines[1]["index"] == 1 and lines[1]["result"]["verdict"] == "supported"
    assert lines[2]["error"]["kind"] == "retrieval_budget"
    assert "budget" in lines[2]["error"]["message"]


def test_stream_fatal_error_is_a_single_error_line_without_done(client):
    use(StreamingFake(fail_with=LLMProviderError("The language model account is out of credit (402).")))

    lines = _ndjson(client.post("/api/v1/analyze/stream", json={"source_text": "x"}))

    assert [l["type"] for l in lines] == ["error"]
    assert lines[0]["error"] == {"kind": "llm", "message": "The language model account is out of credit (402)."}


def test_stream_unexpected_errors_do_not_leak_details(client):
    use(StreamingFake(fail_with=RuntimeError("secret internal detail")))
    lines = _ndjson(client.post("/api/v1/analyze/stream", json={"source_text": "x"}))
    assert lines[0]["error"]["kind"] == "internal"
    assert "secret" not in lines[0]["error"]["message"]


def test_stream_validates_input_before_streaming(client):
    use(StreamingFake())
    assert client.post("/api/v1/analyze/stream", json={"source_text": "   "}).status_code == 422
    assert client.post("/api/v1/analyze/stream", json={}).status_code == 422


@pytest.mark.parametrize("payload", [{}, {"source_text": ""}, {"source_text": "x" * 8001}])
def test_invalid_payload_is_422(client, payload):
    use(FakePipeline(run=PipelineRun()))
    assert client.post("/api/v1/analyze", json=payload).status_code == 422


def test_whitespace_only_is_422(client):
    use(FakePipeline(run=PipelineRun()))
    assert client.post("/api/v1/analyze", json={"source_text": "   "}).status_code == 422


@pytest.mark.parametrize(
    "error,status,needle",
    [
        (RetrievalError("Evidence search failed (ConnectError)."), 502, "source search"),
        (LLMProviderError("The language model timed out."), 502, "timed out"),
        (RuntimeError("secret internal detail"), 500, "RuntimeError"),
    ],
)
def test_pipeline_errors_map_to_http(client, error, status, needle):
    use(FakePipeline(error=error))
    res = client.post("/api/v1/analyze", json={"source_text": "text"})
    assert res.status_code == status
    assert needle in res.json()["detail"]
    assert "secret internal detail" not in res.json()["detail"]


def test_missing_configuration_is_503(client, monkeypatch):
    def fail():
        raise ConfigurationError("OPENROUTER_API_KEY is not set.")

    monkeypatch.setattr(container, "get_pipeline", fail)
    res = client.post("/api/v1/analyze", json={"source_text": "text"})
    assert res.status_code == 503
    assert "OPENROUTER_API_KEY" in res.json()["detail"]


def test_health_reports_readiness(client, monkeypatch):
    monkeypatch.setattr(container, "status", lambda: {"pipeline_ready": False, "pipeline_error": "boom", "info": None})
    body = client.get("/health").json()
    assert body == {"status": "healthy", "pipeline_ready": False, "pipeline_error": "boom", "info": None}


def test_health_exposes_non_secret_configuration(client):
    container._info = {"verdict_mode": "stance", "retrievers": ["wikipedia"], "openalex_key": False,
                       "model": "m", "cache": True}
    try:
        body = client.get("/health").json()
    finally:
        container.reset()
    assert body["info"]["verdict_mode"] == "stance"
    assert "key" not in json.dumps(body).lower().replace("openalex_key", "")


def test_cors_allows_extension_origin_only(client):
    ok = client.options(
        "/api/v1/analyze",
        headers={
            "Origin": "chrome-extension://abcdefghijklmnop",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert ok.headers.get("access-control-allow-origin") == "chrome-extension://abcdefghijklmnop"

    bad = client.options(
        "/api/v1/analyze",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert "access-control-allow-origin" not in bad.headers
