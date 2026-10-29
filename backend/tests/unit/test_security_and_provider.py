import json
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

from app.main import app
from app.services.providers.gemini import GeminiProvider
from app.services.llm_provider import LLMProviderError


@pytest.fixture
def client():
    return TestClient(app)


def test_security_headers_present(client):
    res = client.get("/health")
    assert res.status_code == 200
    assert res.headers["x-content-type-options"] == "nosniff"
    assert res.headers["x-frame-options"] == "DENY"
    assert res.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    assert "accelerometer=()" in res.headers["permissions-policy"]
    assert "strict-transport-security" in res.headers


def test_content_security_policy_on_html(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "content-security-policy" in res.headers
    csp = res.headers["content-security-policy"]
    assert "default-src 'self'" in csp
    assert "frame-ancestors 'none'" in csp


def test_docs_disabled_in_production(client):
    assert client.get("/docs").status_code == 404
    assert client.get("/redoc").status_code == 404
    assert client.get("/openapi.json").status_code == 404


def test_oversized_payload_rejected(client):
    large_payload = {"source_text": "A" * 300000}
    res = client.post("/api/v1/analyze", json=large_payload)
    assert res.status_code == 413
    assert "Payload too large" in res.json()["detail"]


@pytest.mark.asyncio
async def test_provider_validate_empty_key(client):
    res = client.post("/api/v1/provider/validate", json={"provider": "openrouter", "api_key": ""})
    assert res.status_code in (400, 422)


def test_provider_validate_openrouter_mock_success(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        res = client.post("/api/v1/provider/validate", json={"provider": "openrouter", "api_key": "sk-or-test123"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is True
        assert data["provider"] == "openrouter"
        assert "verified" in data["message"].lower()
        # Verify credential is not leaked in output
        assert "sk-or-test123" not in json.dumps(data)


def test_provider_validate_gemini_mock_unauthorized(client):
    with patch("httpx.AsyncClient.get") as mock_get:
        mock_response = AsyncMock()
        mock_response.status_code = 400
        mock_get.return_value = mock_response

        res = client.post("/api/v1/provider/validate", json={"provider": "gemini", "api_key": "AIzaSyFakeKey"})
        assert res.status_code == 200
        data = res.json()
        assert data["valid"] is False
        assert data["provider"] == "gemini"
        assert "unauthorized" in data["message"].lower() or "invalid" in data["message"].lower()
        # Verify credential is not leaked
        assert "AIzaSyFakeKey" not in json.dumps(data)


def test_gemini_provider_init():
    provider = GeminiProvider(api_key="test_key", model="gemini-1.5-flash")
    assert provider.model == "gemini-1.5-flash"
    assert provider._api_key == "test_key"

    with pytest.raises(ValueError):
        GeminiProvider(api_key="")
