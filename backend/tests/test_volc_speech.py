import base64
import gzip
import json
import struct

import httpx
import pytest

from companion_backend.main import create_app
from companion_backend.providers import AsrError, TtsError
from companion_backend.volc_speech import VolcAsr2, VolcTts2


def wav():
    import io
    import wave

    output = io.BytesIO()
    with wave.open(output, "wb") as file:
        file.setnchannels(1)
        file.setsampwidth(2)
        file.setframerate(16000)
        file.writeframes(b"\x30\x00" * 4000)
    return output.getvalue()


def asr_response(body, *, last=False, compressed=True):
    payload = json.dumps(body).encode()
    if compressed:
        payload = gzip.compress(payload)
    return bytes((0x11, 0x93 if last else 0x91, 0x11 if compressed else 0x10, 0)) + struct.pack(">iI", -1 if last else 1, len(payload)) + payload


def test_volc_asr_frames_auth_and_final_text():
    sent = []
    headers_seen = []
    responses = [asr_response({"code": 0}), asr_response({"code": 0}), asr_response({"code": 0, "result": {"text": " 今天我想和朋友玩。 "}}, last=True)]

    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def send(self, payload):
            sent.append(payload)

        def recv(self, *, timeout):
            return responses.pop(0)

    def connect(url, *, additional_headers, **kwargs):
        assert url.endswith("/sauc/bigmodel_nostream")
        headers_seen.append(additional_headers)
        return Socket()

    result = VolcAsr2("secret-for-test", connector=connect, pause=lambda _: None).transcribe(wav(), mime_type="audio/wav")
    assert result == "今天我想和朋友玩。"
    assert headers_seen[0]["X-Api-Resource-Id"] == "volc.seedasr.sauc.duration"
    assert headers_seen[0]["X-Api-Key"] == "secret-for-test"
    assert len(sent) == 3
    assert sent[0][1] == 0x11  # full request, positive sequence
    full = json.loads(gzip.decompress(sent[0][12:]))
    assert full["audio"]["rate"] == 16000 and full["request"]["model_name"] == "bigmodel"
    assert sent[-1][1] == 0x23  # last audio packet, negative sequence
    assert struct.unpack(">i", sent[-1][4:8])[0] == -3
    assert gzip.decompress(sent[1][12:]) == wav()[:6400]


def test_volc_asr_errors_do_not_expose_provider_payload():
    class Socket:
        def __enter__(self):
            return self

        def __exit__(self, *_):
            pass

        def send(self, _):
            pass

        def recv(self, *, timeout):
            return bytes((0x11, 0xF0, 0x10, 0)) + struct.pack(">iI", 4000, 0)

    with pytest.raises(AsrError, match="ASR provider error code 4000") as error:
        VolcAsr2("secret-for-test", connector=lambda *a, **k: Socket()).transcribe(wav(), mime_type="audio/wav")
    assert "secret-for-test" not in str(error.value)


def test_volc_tts_chunks_and_error():
    requests = []

    def respond(request):
        requests.append(request)
        content = b"\n".join([
            json.dumps({"code": 0, "data": base64.b64encode(b"ID3first").decode()}).encode(),
            json.dumps({"code": 0, "data": base64.b64encode(b"second").decode()}).encode(),
            b'{"code": 20000000, "message": "finished"}',
        ])
        return httpx.Response(200, content=content)

    client = httpx.Client(transport=httpx.MockTransport(respond))
    assert VolcTts2("secret-for-test", client=client).synthesize("你好") == b"ID3firstsecond"
    request = requests[0]
    assert str(request.url).endswith("/tts/unidirectional")
    assert request.headers["X-Api-Resource-Id"] == "seed-tts-2.0"
    assert request.headers["X-Api-Key"] == "secret-for-test"
    assert json.loads(request.content)["req_params"]["audio_params"]["format"] == "mp3"

    failed = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b'{"code": 4001, "message": "private provider message"}')))
    with pytest.raises(TtsError, match="TTS provider error code 4001") as error:
        VolcTts2("secret-for-test", client=failed).synthesize("你好")
    assert "private provider message" not in str(error.value)

    forbidden = httpx.Client(transport=httpx.MockTransport(lambda _: httpx.Response(403, content=b"private provider message")))
    with pytest.raises(TtsError, match="TTS HTTP 403") as error:
        VolcTts2("secret-for-test", client=forbidden).synthesize("你好")
    assert "private provider message" not in str(error.value)


def test_volc_key_selects_both_adapters_without_exposing_key(monkeypatch):
    monkeypatch.setenv("VOLC_API_KEY", "secret-for-test")
    app = create_app()
    assert isinstance(app.state.asr, VolcAsr2)
    assert isinstance(app.state.tts, VolcTts2)
