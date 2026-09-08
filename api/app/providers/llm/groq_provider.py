import json

import httpx
from pydantic import ValidationError

from app.providers.llm.base import LLMProvider, LLMProviderError, T

GROQ_CHAT_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"


class GroqProvider(LLMProvider):
    def __init__(self, api_key: str, model: str):
        if not api_key:
            raise LLMProviderError("GROQ_API_KEY is not set")
        self.api_key = api_key
        self.model = model

    async def _call(self, system_prompt: str, user_prompt: str) -> str:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                GROQ_CHAT_ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.7,
                },
            )
        if response.status_code >= 400:
            raise LLMProviderError(f"Groq request failed ({response.status_code}): {response.text}")

        body = response.json()
        try:
            return body["choices"][0]["message"]["content"]
        except (KeyError, IndexError) as exc:
            raise LLMProviderError(f"Unexpected Groq response shape: {body}") from exc

    async def generate_structured(
        self, system_prompt: str, user_prompt: str, response_model: type[T]
    ) -> T:
        content = await self._call(system_prompt, user_prompt)

        try:
            return response_model.model_validate_json(content)
        except (ValidationError, json.JSONDecodeError) as first_error:
            # One retry with the validation error fed back — real models occasionally
            # drop a required field or emit invalid JSON on the first pass.
            retry_prompt = (
                f"{user_prompt}\n\nYour previous response failed validation with this error:\n"
                f"{first_error}\n\nReturn ONLY valid JSON matching the required schema exactly."
            )
            content = await self._call(system_prompt, retry_prompt)
            try:
                return response_model.model_validate_json(content)
            except (ValidationError, json.JSONDecodeError) as second_error:
                raise LLMProviderError(
                    f"Groq output failed schema validation twice: {second_error}"
                ) from second_error
