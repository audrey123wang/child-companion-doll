"""Volcengine Seed ASR 2.0 and TTS 2.0 adapters for the local prototype."""

from __future__ import annotations

import base64
import binascii
import gzip
import json
import struct
import time
import uuid
from typing import Callable

import httpx
from websockets.sync.client import connect
from websockets.exceptions import InvalidStatus

from .providers import AsrError, TtsError


ASR_URL = "wss://openspeech.bytedance.com/api/v3/sauc/bigmodel_nostream"
TTS_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"
ASR_RESOURCE = "volc.seedasr.sauc.duration"
TTS_RESOURCE = "seed-tts-2.0"
DEFAULT_SPEAKER = "zh_female_vv_uranus_bigtts"


def _frame(message_type: int, flags: int, payload: bytes, sequence: int) -> bytes:
    compressed = gzip.compress(payload)
    serialization = 0x10 if message_type == 1 else 0x00
    return (
        bytes((0x11, (message_type << 4) | flags, serialization | 0x01, 0))
        + struct.pack(">iI", sequence, len(compressed)) + compressed
    )


def _response(data: bytes) -> tuple[bool, dict]:
    if not isinstance(data, bytes) or len(data) < 8 or data[0] >> 4 != 1:
        raise AsrError("invalid ASR response")
    header_size = (data[0] & 0x0F) * 4
    message_type, flags = data[1] >> 4, data[1] & 0x0F
    cursor = header_size
    if header_size < 4 or len(data) < cursor + 4:
        raise AsrError("invalid ASR response")
    if flags & 1:
        cursor += 4  # response sequence
    if flags & 4:
        cursor += 4  # event
    if message_type == 0xF:
        code = int.from_bytes(data[cursor:cursor + 4], "big") if len(data) >= cursor + 4 else None
        raise AsrError(f"ASR provider error code {code}" if code is not None else "ASR provider failed")
    if message_type != 9 or len(data) < cursor + 4:
        raise AsrError("invalid ASR response")
    size = int.from_bytes(data[cursor:cursor + 4], "big")
    cursor += 4
    if size > 1_000_000 or len(data) != cursor + size:
        raise AsrError("invalid ASR response")
    payload = data[cursor:]
    if data[2] & 0x0F == 1:
        try:
            payload = gzip.decompress(payload)
        except (OSError, EOFError) as exc:
            raise AsrError("invalid ASR response") from exc
    if data[2] >> 4 != 1:
        raise AsrError("invalid ASR response")
    try:
        body = json.loads(payload)
    except (ValueError, UnicodeDecodeError) as exc:
        raise AsrError("invalid ASR response") from exc
    if not isinstance(body, dict):
        raise AsrError("invalid ASR response")
    if body.get("code", 0) != 0:
        code = body.get("code")
        raise AsrError(f"ASR provider error code {code}" if isinstance(code, int) else "ASR provider failed")
    return bool(flags & 2), body


class VolcAsr2:
    def __init__(
        self, api_key: str, *, resource_id: str = ASR_RESOURCE,
        connector: Callable | None = None, pause: Callable[[float], None] = time.sleep,
    ):
        if not api_key:
            raise ValueError("API key is required")
        self._key = api_key
        self._resource = resource_id
        self._connect = connector or connect
        self._pause = pause

    def transcribe(self, audio: bytes, *, mime_type: str) -> str:
        if mime_type != "audio/wav" or len(audio) < 44 or audio[:4] != b"RIFF":
            raise AsrError("16 kHz PCM WAV required")
        request_id = str(uuid.uuid4())
        headers = {
            "X-Api-Key": self._key,
            "X-Api-Resource-Id": self._resource,
            "X-Api-Request-Id": request_id,
            "X-Api-Connect-Id": request_id,
            "X-Api-Sequence": "-1",
        }
        body = {
            "user": {"uid": request_id},
            "audio": {"format": "wav", "codec": "raw", "rate": 16000, "bits": 16, "channel": 1},
            "request": {"model_name": "bigmodel", "enable_itn": True, "enable_punc": True},
        }
        chunks = [audio[i:i + 6400] for i in range(0, len(audio), 6400)]
        try:
            with self._connect(ASR_URL, additional_headers=headers, open_timeout=10, close_timeout=5) as ws:
                ws.send(_frame(1, 1, json.dumps(body).encode(), 1))
                _response(ws.recv(timeout=15))
                final_body = None
                for number, chunk in enumerate(chunks, start=2):
                    last = number == len(chunks) + 1
                    ws.send(_frame(2, 3 if last else 1, chunk, -number if last else number))
                    is_final, response = _response(ws.recv(timeout=45))
                    if last:
                        if not is_final:
                            raise AsrError("ASR final response missing")
                        final_body = response
                    elif not is_final:
                        self._pause(0.2)
        except AsrError:
            raise
        except InvalidStatus as exc:
            status = exc.response.status_code
            raise AsrError(f"ASR WebSocket handshake HTTP {status}") from exc
        except TimeoutError as exc:
            raise AsrError("ASR provider timeout") from exc
        except Exception as exc:
            # Expose only the exception class. Its message may contain request metadata.
            raise AsrError(f"ASR client error {type(exc).__name__}") from exc
        result = (final_body or {}).get("result")
        value = result.get("text") if isinstance(result, dict) else None
        if not isinstance(value, str) or not value.strip():
            raise AsrError("transcription was empty")
        return value.strip()


class VolcTts2:
    def __init__(
        self, api_key: str, *, speaker: str = DEFAULT_SPEAKER,
        client: httpx.Client | None = None,
    ):
        if not api_key or not speaker:
            raise ValueError("API key and speaker are required")
        self._key = api_key
        self._speaker = speaker
        self._client = client or httpx.Client(timeout=45.0)

    def synthesize(self, text: str) -> bytes:
        audio = bytearray()
        try:
            with self._client.stream(
                "POST", TTS_URL,
                headers={
                    "X-Api-Key": self._key,
                    "X-Api-Resource-Id": TTS_RESOURCE,
                    "X-Api-Request-Id": str(uuid.uuid4()),
                },
                json={"req_params": {
                    "text": text, "speaker": self._speaker,
                    "audio_params": {"format": "mp3", "sample_rate": 24000},
                }},
            ) as response:
                response.raise_for_status()
                for line in response.iter_lines():
                    if not line:
                        continue
                    item = json.loads(line)
                    if not isinstance(item, dict):
                        raise TtsError("invalid speech response")
                    code = item.get("code")
                    if code == 20000000:
                        break
                    if code != 0:
                        raise TtsError(f"TTS provider error code {code}" if isinstance(code, int) else "speech provider failed")
                    data = item.get("data")
                    if data:
                        audio.extend(base64.b64decode(data, validate=True))
                        if len(audio) > 2_000_000:
                            raise TtsError("speech response size invalid")
        except TtsError:
            raise
        except httpx.HTTPStatusError as exc:
            raise TtsError(f"TTS HTTP {exc.response.status_code}") from exc
        except (httpx.HTTPError, ValueError, TypeError, binascii.Error) as exc:
            raise TtsError("speech provider failed") from exc
        if not audio:
            raise TtsError("speech response was empty")
        return bytes(audio)
