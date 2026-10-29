import json

import httpx
import pytest
from pydantic import BaseModel

from app.services.providers.openrouter import LLMProviderError, OpenRouterProvider

SECRET = "sk-or-v1-TESTSECRET"


class Answer(BaseModel):
    value: int


def _provider(handler, **kwargs) -> OpenRouterProvider:
    client = httpx.AsyncClient(base_url="https://example.test/api/v1", transport=httpx.MockTransport(handler))
    return OpenRouterProvider(api_key=SECRET, model="test/model", client=client, **kwargs)


def _reply(content: str, status: int = 200) -> httpx.Response:
    return httpx.Response(status, json={"choices": [{"message": {"content": content}}]})


@pytest.mark.asyncio
async def test_parses_json_and_sends_auth_and_schema():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content)
        return _reply('{"value": 7}')

    result = await _provider(handler).generate_structured_output("question", Answer)

    assert result == Answer(value=7)
    assert seen["auth"] == f"Bearer {SECRET}"
    assert seen["body"]["model"] == "test/model"
    assert seen["body"]["temperature"] == 0
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "value" in seen["body"]["messages"][0]["content"]  # schema embedded in system prompt


@pytest.mark.asyncio
async def test_accepts_fenced_json():
    provider = _provider(lambda r: _reply('```json\n{"value": 3}\n```'))
    assert (await provider.generate_structured_output("q", Answer)).value == 3


@pytest.mark.asyncio
async def test_repairs_invalid_reply_once():
    replies = iter(['{"value": "not a number"}', '{"value": 5}'])
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(json.loads(request.content)["messages"])
        return _reply(next(replies))

    result = await _provider(handler).generate_structured_output("q", Answer)

    assert result.value == 5
    assert len(calls) == 2
    assert "invalid" in calls[1][-1]["content"]


@pytest.mark.asyncio
async def test_gives_up_after_repair_attempts():
    provider = _provider(lambda r: _reply("no json here"), max_repair_attempts=1)
    with pytest.raises(LLMProviderError, match="Answer"):
        await provider.generate_structured_output("q", Answer)


@pytest.mark.asyncio
async def test_retries_rate_limit_then_succeeds():
    statuses = iter([429, 200])

    def handler(request: httpx.Request) -> httpx.Response:
        return _reply('{"value": 1}') if next(statuses) == 200 else httpx.Response(429)

    assert (await _provider(handler).generate_structured_output("q", Answer)).value == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("status,needle", [(401, "API key"), (402, "credit"), (500, "500")])
async def test_http_errors_are_mapped_and_never_leak_the_key(status, needle):
    provider = _provider(lambda r: httpx.Response(status, text=f"echo {SECRET}"), max_transport_retries=0)
    with pytest.raises(LLMProviderError) as exc:
        await provider.generate_structured_output("q", Answer)
    assert needle in str(exc.value)
    assert SECRET not in str(exc.value)


@pytest.mark.asyncio
async def test_unexpected_response_shape():
    provider = _provider(lambda r: httpx.Response(200, json={"unexpected": True}))
    with pytest.raises(LLMProviderError, match="unexpected"):
        await provider.generate_structured_output("q", Answer)


@pytest.mark.asyncio
async def test_counts_calls_and_tokens():
    def handler(request):
        return httpx.Response(200, json={
            "choices": [{"message": {"content": '{"value": 1}'}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 8},
        })

    provider = _provider(handler)
    await provider.generate_structured_output("q", Answer)
    await provider.generate_structured_output("q", Answer)
    assert (provider.calls, provider.prompt_tokens, provider.completion_tokens) == (2, 240, 16)


@pytest.mark.asyncio
async def test_generate_text_uses_requested_model_without_json_mode():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return _reply("  Paris is the capital of France.  ")

    provider = _provider(handler)
    text = await provider.generate_text("Capital of France?", model="other/model", system="Be brief.", max_tokens=50)

    assert text == "Paris is the capital of France."
    assert seen["body"]["model"] == "other/model"
    assert seen["body"]["max_tokens"] == 50
    assert "response_format" not in seen["body"]
    assert [m["role"] for m in seen["body"]["messages"]] == ["system", "user"]


@pytest.mark.asyncio
async def test_structured_calls_still_use_default_model_and_json_mode():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return _reply('{"value": 1}')

    await _provider(handler).generate_structured_output("q", Answer)
    assert seen["body"]["model"] == "test/model"
    assert seen["body"]["response_format"] == {"type": "json_object"}
    assert "max_tokens" not in seen["body"]


def test_requires_api_key():
    with pytest.raises(ValueError):
        OpenRouterProvider(api_key="")
