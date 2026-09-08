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
