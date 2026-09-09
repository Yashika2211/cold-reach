import json

import httpx
import pytest
import respx
from pydantic import BaseModel

from app.providers.llm.base import LLMProviderError
from app.providers.llm.groq_provider import GroqProvider


class SampleSchema(BaseModel):
    subject: str
    body: str


@pytest.mark.asyncio
@respx.mock
async def test_generate_structured_parses_valid_json():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"subject": "hi", "body": "hello there"})}}
                ]
            },
        )
    )

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b")
    result = await provider.generate_structured("system", "user", SampleSchema)

    assert result.subject == "hi"
    assert result.body == "hello there"


@pytest.mark.asyncio
@respx.mock
async def test_generate_structured_retries_once_on_invalid_json_then_succeeds():
    route = respx.post("https://api.groq.com/openai/v1/chat/completions")
    route.side_effect = [
        httpx.Response(200, json={"choices": [{"message": {"content": "not valid json"}}]}),
        httpx.Response(
            200,
            json={
                "choices": [
                    {"message": {"content": json.dumps({"subject": "hi", "body": "fixed"})}}
                ]
            },
        ),
    ]

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b")
    result = await provider.generate_structured("system", "user", SampleSchema)

    assert result.body == "fixed"
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_generate_structured_raises_after_two_failures():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(200, json={"choices": [{"message": {"content": "still not json"}}]})
    )

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b")
    with pytest.raises(LLMProviderError):
        await provider.generate_structured("system", "user", SampleSchema)


def test_missing_api_key_raises_immediately():
    with pytest.raises(LLMProviderError):
        GroqProvider(api_key="", model="openai/gpt-oss-120b")


@pytest.mark.asyncio
@respx.mock
async def test_groq_error_response_raises_llm_provider_error():
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(401, json={"error": "invalid api key"})
    )

    provider = GroqProvider(api_key="bad-key", model="openai/gpt-oss-120b")
    with pytest.raises(LLMProviderError):
        await provider.generate_structured("system", "user", SampleSchema)


@pytest.mark.asyncio
@respx.mock
async def test_error_message_extracted_from_nested_groq_error_shape():
    """Real Groq errors nest as {"error": {"message": ...}} — this must surface as a
    clean sentence (it ends up displayed directly in the review queue UI), not the
    raw JSON body with escaped quotes."""
    respx.post("https://api.groq.com/openai/v1/chat/completions").mock(
        return_value=httpx.Response(
            429,
            json={
                "error": {
                    "message": "Rate limit reached for model. Please try again in 6.5s.",
                    "type": "tokens",
                    "code": "rate_limit_exceeded",
                }
            },
        )
    )

    provider = GroqProvider(api_key="test-key", model="openai/gpt-oss-120b")
    with pytest.raises(LLMProviderError) as exc_info:
        await provider.generate_structured("system", "user", SampleSchema)

    message = str(exc_info.value)
    assert "Rate limit reached for model. Please try again in 6.5s." in message
    assert '"error"' not in message
    assert "\\" not in message
