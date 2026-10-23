"""
The "generation" half of RAG: an LLM writes the answer from the
retrieved notes. Kept behind a tiny interface so the provider can be
swapped (Gemini today; Claude, OpenAI or a local model later) by adding
one class here, with no other code changes.

Gemini is called with plain HTTP (no SDK) to keep dependencies minimal.
"""
from typing import Protocol

import httpx

from app.core.config import settings
from app.core.exceptions import AppError

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


class LLMProviderError(AppError):
    """Any provider failure: no key, rate limit, network, bad response.
    The chat service catches this and falls back to knowledge-base answers."""


class LLMProvider(Protocol):
    name: str

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        """messages: [{"role": "user" | "assistant", "content": str}, ...]"""
        ...


class GeminiProvider:
    name = "gemini"

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    def generate(self, system_prompt: str, messages: list[dict]) -> str:
        body = {
            "system_instruction": {"parts": [{"text": system_prompt}]},
            "contents": [
                # Gemini calls the assistant role "model"
                {"role": "model" if m["role"] == "assistant" else "user", "parts": [{"text": m["content"]}]}
                for m in messages
            ],
            "generationConfig": {"temperature": 0.3, "maxOutputTokens": 700},
        }
        try:
            resp = httpx.post(
                GEMINI_URL.format(model=self.model),
                headers={"x-goog-api-key": self.api_key},  # header, so the key never appears in logged URLs
                json=body,
                timeout=settings.LLM_TIMEOUT_SECONDS,
            )
        except httpx.HTTPError as e:
            raise LLMProviderError(f"Gemini unreachable: {e!r}") from e

        if resp.status_code == 429:
            raise LLMProviderError("Gemini rate limit reached")
        if resp.status_code != 200:
            raise LLMProviderError(f"Gemini error {resp.status_code}: {resp.text[:300]}")

        try:
            parts = resp.json()["candidates"][0]["content"]["parts"]
            text = "".join(p.get("text", "") for p in parts).strip()
        except (KeyError, IndexError, ValueError) as e:  # e.g. response blocked by safety filters
            raise LLMProviderError(f"Unexpected Gemini response: {resp.text[:300]}") from e
        if not text:
            raise LLMProviderError("Gemini returned an empty answer")
        return text


def get_provider() -> LLMProvider | None:
    """None means "no AI configured": the chatbot answers straight from
    the knowledge base. Adding a key in .env switches AI answers on."""
    if settings.GEMINI_API_KEY:
        return GeminiProvider(settings.GEMINI_API_KEY, settings.GEMINI_MODEL)
    return None
