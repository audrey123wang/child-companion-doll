"""Provider ports and an opt-in file transcription adapter."""

import httpx
from typing import Protocol


class AsrProvider(Protocol):
    def transcribe(self, audio: bytes, *, mime_type: str) -> str: ...


class AsrError(Exception):
    """The remote transcription did not return usable text."""


class OpenAIAsr:
    def __init__(self, api_key: str, *, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("API key is required")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=45.0)

    def transcribe(self, audio: bytes, *, mime_type: str) -> str:
        try:
            response = self._client.post(
                "https://api.openai.com/v1/audio/transcriptions",
                headers={"Authorization": f"Bearer {self._api_key}"},
                data={"model": "gpt-transcribe", "languages[]": "zh"},
                files={"file": ("voice.wav", audio, mime_type)},
            )
            response.raise_for_status()
            text = response.json().get("text", "")
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            # Do not include provider response bodies, audio, or headers in logs.
            raise AsrError("transcription provider failed") from exc
        if not isinstance(text, str) or not text.strip():
            raise AsrError("transcription was empty")
        return text.strip()


class TextProvider(Protocol):
    def complete(self, prompt: str, *, schema_name: str) -> dict: ...


class TtsProvider(Protocol):
    def synthesize(self, text: str) -> bytes: ...


class TtsError(Exception):
    """The speech provider did not return playable audio."""


class OpenAITts:
    def __init__(self, api_key: str, *, client: httpx.Client | None = None):
        if not api_key:
            raise ValueError("API key is required")
        self._api_key = api_key
        self._client = client or httpx.Client(timeout=45.0)

    def synthesize(self, text: str) -> bytes:
        try:
            response = self._client.post(
                "https://api.openai.com/v1/audio/speech",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={
                    "model": "gpt-4o-mini-tts", "voice": "coral", "input": text,
                    "instructions": "用自然、温柔、清楚的普通话朗读。保持适合儿童的平稳语速。",
                    "response_format": "mp3",
                },
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise TtsError("speech provider failed") from exc
        if not response.content or len(response.content) > 2_000_000:
            raise TtsError("speech response size invalid")
        if not response.headers.get("content-type", "").startswith(("audio/", "application/octet-stream")):
            raise TtsError("speech response was not audio")
        return response.content
