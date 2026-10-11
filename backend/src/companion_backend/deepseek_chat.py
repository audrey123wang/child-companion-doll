"""DeepSeek V4 Pro text generation for the local child conversation experiment."""

from __future__ import annotations

from typing import Protocol

import httpx


class ChatError(Exception):
    """Text model failed without exposing child content or provider response bodies."""


class ChatProvider(Protocol):
    def complete(self, messages: list[dict[str, str]]) -> str: ...


class DeepSeekV4:
    URL = "https://api.deepseek.com/chat/completions"

    def __init__(self, api_key: str, *, model: str = "deepseek-v4-pro", client: httpx.Client | None = None):
        if not api_key or not model:
            raise ValueError("DeepSeek API key and model are required")
        self._key = api_key
        self._model = model
        self._client = client or httpx.Client(timeout=45.0)

    def complete(self, messages: list[dict[str, str]]) -> str:
        try:
            response = self._client.post(
                self.URL,
                headers={"Authorization": f"Bearer {self._key}"},
                json={
                    "model": self._model, "messages": messages,
                    "thinking": {"type": "disabled"}, "max_tokens": 256,
                    "stream": False,
                },
            )
            response.raise_for_status()
            body = response.json()
            result = body["choices"][0]["message"]["content"]
        except httpx.HTTPStatusError as exc:
            raise ChatError(f"LLM HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError, KeyError, IndexError, TypeError) as exc:
            raise ChatError("LLM provider failed") from exc
        if not isinstance(result, str) or not result.strip():
            raise ChatError("LLM returned empty reply")
        return result.strip()
