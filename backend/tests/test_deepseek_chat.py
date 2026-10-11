"""The child Q&A path must return text before speech and keep secrets out of errors."""

from datetime import datetime, timezone, timedelta
import io
import json
import wave

import httpx
from fastapi.testclient import TestClient

from companion_backend.deepseek_chat import ChatError, DeepSeekV4
from companion_backend.main import create_app
from companion_backend.service import SceneService
from companion_backend.stories import STORY_ID


CHILD = {"Authorization": "Bearer local-child-token"}
SAMPLE = {"child_id": "child-1", "device_id": "device-1", "segment_id": "seg-1",
          "text": "今天为什么甜甜不跟我玩儿，去跟裙裙玩儿了"}


def test_deepseek_v4_request_shape_and_error_sanitization():
    def respond(request: httpx.Request) -> httpx.Response:
        assert str(request.url) == "https://api.deepseek.com/chat/completions"
        assert request.headers["Authorization"] == "Bearer test-only-secret"
        body = json.loads(request.content)
        assert body["model"] == "deepseek-v4-pro"
        assert body["thinking"] == {"type": "disabled"}
        assert body["messages"] == [{"role": "user", "content": "你好"}]
        return httpx.Response(200, json={"choices": [{"message": {"content": "你好呀。"}}]})

    model = DeepSeekV4("test-only-secret", client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert model.complete([{"role": "user", "content": "你好"}]) == "你好呀。"

    failed = DeepSeekV4("test-only-secret", client=httpx.Client(
        transport=httpx.MockTransport(lambda _: httpx.Response(401, text="private provider body"))))
    try:
        failed.complete([{"role": "user", "content": "你好"}])
    except ChatError as exc:
        assert "401" in str(exc)
        assert "private provider body" not in str(exc)
        assert "test-only-secret" not in str(exc)
    else:
        raise AssertionError("provider failure should raise")


def test_text_first_then_tts_with_daily_context_and_session_history():
    clock = [datetime(2026, 10, 11, 12, tzinfo=timezone.utc)]  # 20:00 Shanghai
    service = SceneService(now=lambda: clock[0])
    service.submit_synthetic(**SAMPLE)

    class Model:
        calls = []
        def complete(self, messages):
            self.calls.append(messages)
            return "听起来你有点难过。你想和我说说当时发生了什么吗？"

    class Tts:
        calls = []
        def synthesize(self, text):
            self.calls.append(text)
            return b"mp3-data"

    model, tts = Model(), Tts()
    client = TestClient(create_app(service, chat_provider=model, tts_provider=tts))
    body = {"child_id": "child-1", "story_id": STORY_ID, "text": "我想知道为什么她不跟我玩"}
    response = client.post("/v1/child/chat-turns", json=body, headers=CHILD)
    assert response.status_code == 200, response.text
    first = response.json()
    assert first["reply_text"].startswith("听起来")
    assert first["tts_status"] == "pending"
    assert first["reply_id"] and first["session_id"]
    assert tts.calls == []
    assert "同伴" in model.calls[0][0]["content"]
    assert model.calls[0][-1] == {"role": "user", "content": body["text"]}

    speech = client.post(f"/v1/child/chat-turns/{first['reply_id']}/speech",
                         params={"child_id": "child-1"}, headers=CHILD)
    assert speech.status_code == 200 and speech.content == b"mp3-data"
    assert speech.headers["content-type"] == "audio/mpeg"
    assert tts.calls == [first["reply_text"]]
    assert client.post(f"/v1/child/chat-turns/{first['reply_id']}/speech",
                       params={"child_id": "child-2"}, headers=CHILD).status_code == 404

    body.update({"text": "我当时先去找了别人", "session_id": first["session_id"]})
    second = client.post("/v1/child/chat-turns", json=body, headers=CHILD)
    assert second.status_code == 200
    assert model.calls[1][-3:] == [
        {"role": "user", "content": "我想知道为什么她不跟我玩"},
        {"role": "assistant", "content": first["reply_text"]},
        {"role": "user", "content": "我当时先去找了别人"},
    ]
    clock[0] += timedelta(minutes=21)
    assert client.post(f"/v1/child/chat-turns/{first['reply_id']}/speech",
                       params={"child_id": "child-1"}, headers=CHILD).status_code == 404


def test_model_failure_does_not_consume_turn_and_stop_bypasses_model():
    service = SceneService(now=lambda: datetime(2026, 10, 11, 12, tzinfo=timezone.utc))
    service.submit_synthetic(**SAMPLE)

    class Model:
        calls = 0
        fail = True
        def complete(self, messages):
            self.calls += 1
            if self.fail:
                raise ChatError("LLM provider failed")
            return "我们可以先说说你最想和朋友一起玩什么。"

    model = Model()
    client = TestClient(create_app(service, chat_provider=model))
    body = {"child_id": "child-1", "story_id": STORY_ID, "text": "朋友没跟我玩怎么办"}
    assert client.post("/v1/child/chat-turns", json=body, headers=CHILD).status_code == 502
    model.fail = False
    result = client.post("/v1/child/chat-turns", json=body, headers=CHILD)
    assert result.status_code == 200 and result.json()["turn_number"] == 1
    body.update({"text": "不想聊了", "session_id": result.json()["session_id"]})
    stopped = client.post("/v1/child/chat-turns", json=body, headers=CHILD)
    assert stopped.status_code == 200 and stopped.json()["route"] == "stopped"
    assert model.calls == 2


def test_chat_requires_model_when_not_in_synthetic_mode(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    service = SceneService(now=lambda: datetime(2026, 10, 11, 12, tzinfo=timezone.utc))
    service.submit_synthetic(**SAMPLE)
    client = TestClient(create_app(service, synthetic_enabled=False))
    body = {"child_id": "child-1", "story_id": STORY_ID, "text": "朋友没跟我玩怎么办"}
    assert client.post("/v1/child/chat-turns", json=body, headers=CHILD).status_code == 503


def test_transcribe_only_returns_recognized_text_without_starting_chat():
    class Asr:
        def transcribe(self, audio, *, mime_type):
            assert mime_type == "audio/wav"
            return "我想找朋友一起玩"

    class Model:
        calls = 0
        def complete(self, messages):
            self.calls += 1
            return "你好。"

    model = Model()
    client = TestClient(create_app(SceneService(), asr_provider=Asr(), chat_provider=model))
    stream = io.BytesIO()
    with wave.open(stream, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\xe8\x03" * 8000)
    response = client.post("/v1/child/chat-turns/transcribe", content=stream.getvalue(),
                           headers={**CHILD, "X-Child-ID": "child-1", "Content-Type": "audio/wav"})
    assert response.status_code == 200 and response.json() == {"heard_text": "我想找朋友一起玩"}
    assert model.calls == 0


def test_local_story_page_uses_tts_and_child_scope():
    class Tts:
        calls = []
        def synthesize(self, text):
            self.calls.append(text)
            return b"story-mp3"

    service = SceneService()
    service.set_profile(child_id="child-1", age=7, school_stage="grade_1", listening_start=None, listening_end=None)
    tts = Tts()
    client = TestClient(create_app(service, tts_provider=tts))
    body = {"child_id": "child-1", "story_id": "friendship-bear", "page": 0,
            "text": "小熊在树下和新朋友玩。"}
    result = client.post("/v1/child/story-narration", json=body, headers=CHILD)
    assert result.status_code == 200 and result.content == b"story-mp3"
    assert result.headers["X-AI-Generated-Voice"] == "true"
    assert tts.calls == [body["text"]]
    assert client.post("/v1/child/story-narration", json={**body, "child_id": "child-2"}, headers=CHILD).status_code == 403
    assert client.post("/v1/child/story-narration", json={**body, "story_id": "unknown"}, headers=CHILD).status_code == 422
