from datetime import datetime, timezone
import asyncio
import base64
import io
import os
import sqlite3
import wave

os.environ["APP_ENV"] = "local"

from fastapi.testclient import TestClient
import httpx

from companion_backend.main import create_app
from companion_backend.domain import extract_sample_event
from companion_backend.providers import OpenAIAsr, OpenAITts
from companion_backend.service import SceneService
from companion_backend.stories import STORY_ID


PARENT = {"Authorization": "Bearer local-parent-token"}
CHILD = {"Authorization": "Bearer local-child-token"}
DEVICE = {"Authorization": "Bearer local-device-token"}
SAMPLE = {"child_id": "child-1", "device_id": "device-1", "segment_id": "seg-1", "text": "今天为什么甜甜不跟我玩儿，去跟裙裙玩儿了"}


def make_client(clock):
    return TestClient(create_app(SceneService(now=lambda: clock[0]), synthetic_enabled=True))


def configure_local_device(client, *, child_id="child-1", device_id="device-1"):
    profile = client.put("/v1/parent/profile", json={
        "child_id": child_id, "age": 7, "school_stage": "grade_1",
        "listening_start": "08:00", "listening_end": "20:00",
    }, headers=PARENT)
    assert profile.status_code == 200
    assert client.put("/v1/parent/device-binding", json={"child_id": child_id, "device_id": device_id}, headers=PARENT).status_code == 200
    assert client.put("/v1/parent/button-recording", json={"child_id": child_id, "enabled": True}, headers=PARENT).status_code == 200


def test_ingest_report_idempotency_and_role_isolation():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]  # 20:00 Shanghai
    client = make_client(clock)
    first = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    assert first.status_code == 200
    body = first.json()
    assert "甜甜" in body["transcript"]
    assert "裙裙" in body["transcript"]
    again = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    assert again.json()["event_id"] == body["event_id"]
    assert client.post("/v1/dev/segments/text", json={**SAMPLE, "child_id": "another-child"}, headers=DEVICE).status_code == 409
    report = client.get("/v1/parent/reports/daily", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()
    assert report["event_count"] == 1
    assert "不知道其他孩子" in report["unknowns"][0]
    assert "甜甜" not in str(report)
    assert client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=CHILD).status_code == 403


def test_midnight_expiry_and_delete_recomputes_report():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    event_id = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE).json()["event_id"]
    clock[0] = datetime(2026, 10, 11, 16, 1, tzinfo=timezone.utc)  # 00:01 Shanghai
    inputs = client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()
    assert inputs["items"][0]["transcript"] is None
    assert inputs["items"][0]["summary"]
    assert client.app.state.service._segments[("device-1", "seg-1")]["transcript"] is None
    assert client.delete(f"/v1/parent/events/{event_id}", params={"child_id": "child-1"}, headers=PARENT).status_code == 200
    report = client.get("/v1/parent/reports/daily", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()
    assert report["event_count"] == 0
    assert report["status"] == "insufficient"


def test_chat_stop_and_real_audio_fails_closed():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    result = client.post("/v1/child/chat-turns", json={"child_id": "child-1", "story_id": STORY_ID, "text": "我不想聊了"}, headers=CHILD).json()
    assert result["route"] == "stopped"
    assert result["tts_status"] == "not_configured"
    configure_local_device(client)
    headers = {**DEVICE, "X-Device-ID": "device-1", "X-Segment-ID": "seg-1", "Content-Type": "audio/wav"}
    assert client.post("/v1/device/segments", content=b"not-real-audio", headers=headers).status_code == 503


def test_audio_ingress_with_injected_asr_and_idempotency():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]

    class FakeAsr:
        calls = 0
        def transcribe(self, audio: bytes, *, mime_type: str) -> str:
            self.calls += 1
            assert mime_type == "audio/wav"
            return SAMPLE["text"]

    asr = FakeAsr()
    app = create_app(SceneService(now=lambda: clock[0]), synthetic_enabled=False, asr_provider=asr)
    client = TestClient(app)
    configure_local_device(client)
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\xe8\x03" * 8000)
    headers = {**DEVICE, "X-Device-ID": "device-1", "X-Segment-ID": "seg-audio-1", "X-Child-ID": "wrong-child", "Content-Type": "audio/wav"}
    first = client.post("/v1/device/segments", content=wav.getvalue(), headers=headers)
    assert first.status_code == 200
    assert "甜甜" in first.json()["transcript"]
    assert client.post("/v1/device/segments", content=wav.getvalue(), headers=headers).json()["event_id"] == first.json()["event_id"]
    assert asr.calls == 1
    assert first.json()["event_id"] in client.app.state.service._events
    assert client.app.state.service._events[first.json()["event_id"]]["child_id"] == "child-1"
    assert client.post("/v1/device/segments", content=b"invalid", headers=headers).status_code == 422


def test_openai_asr_request_shape_without_external_call():
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/transcriptions"
        body = request.content
        assert b"gpt-transcribe" in body and b"languages[]" in body and b"zh" in body
        assert b"voice.wav" in body
        return httpx.Response(200, json={"text": "今天为什么甜甜不跟我玩儿"})

    client = httpx.Client(transport=httpx.MockTransport(respond))
    provider = OpenAIAsr("test-key", client=client)
    assert "甜甜" in provider.transcribe(b"synthetic-wav", mime_type="audio/wav")


def test_non_local_requests_are_rejected():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    app = create_app(SceneService(now=lambda: clock[0]), synthetic_enabled=True)
    async def request_from_remote():
        transport = httpx.ASGITransport(app=app, client=("8.8.8.8", 1234))
        async with httpx.AsyncClient(transport=transport, base_url="http://example.com") as client:
            return await client.get("/healthz")
    assert asyncio.run(request_from_remote()).status_code == 403


def test_sqlite_reopen_and_physical_transcript_expiry(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    first = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    saved = first.submit_synthetic(**SAMPLE)
    assert saved["transcript"] == SAMPLE["text"]
    first._store.close()

    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    assert reopened.report(child_id="child-1", day=datetime(2026, 10, 11).date())["event_count"] == 1
    assert reopened.inputs(child_id="child-1", day=datetime(2026, 10, 11).date())[0]["transcript"] == SAMPLE["text"]
    reopened._store.close()

    clock[0] = datetime(2026, 10, 11, 16, 1, tzinfo=timezone.utc)
    expired = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    assert expired.inputs(child_id="child-1", day=datetime(2026, 10, 11).date())[0]["transcript"] is None
    expired._store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT transcript FROM segments").fetchone()[0] is None


def test_sqlite_delete_persists_and_removes_transcript(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    event_id = service.submit_synthetic(**SAMPLE)["event_id"]
    service.revise_event(child_id="child-1", event_id=event_id, delete=True)
    service._store.close()
    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    assert reopened.report(child_id="child-1", day=datetime(2026, 10, 11).date())["event_count"] == 0
    assert reopened.inputs(child_id="child-1", day=datetime(2026, 10, 11).date()) == []
    reopened._store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT transcript FROM segments").fetchone()[0] is None


def test_1900_report_materializes_and_revises(tmp_path):
    clock = [datetime(2026, 10, 11, 10, 59, tzinfo=timezone.utc)]  # 18:59 Shanghai
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    event_id = service.submit_synthetic(**SAMPLE)["event_id"]
    assert service.generate_due_reports() == 0
    clock[0] = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    assert service.generate_due_reports() == 1
    assert service.generate_due_reports() == 0
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT revision FROM reports").fetchone()[0] == 1
    service.revise_event(child_id="child-1", event_id=event_id, summary="家长核对后确认只是没听清游戏邀请")
    assert service.generate_due_reports() == 1
    assert service.report(child_id="child-1", day=datetime(2026, 10, 11).date())["revision"] == 2
    service._store.close()


def test_story_recommendation_uses_active_event_and_age():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    url = "/v1/child/story/today"
    assert client.get(url, params={"child_id": "child-1", "age": 7}, headers=CHILD).json()["status"] == "no_recommendation"
    event_id = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE).json()["event_id"]
    titles = set()
    for age, band in [(6, "5-7"), (9, "8-10"), (12, "11-12")]:
        story = client.get(url, params={"child_id": "child-1", "age": age}, headers=CHILD).json()["story"]
        assert story["age_band"] == band
        assert story["approved"] is False
        assert "甜甜" not in str(story) and "裙裙" not in str(story)
        titles.add(story["title"])
    assert len(titles) == 3
    assert client.get(url, params={"child_id": "another-child", "age": 7}, headers=CHILD).json()["story"] is None
    client.delete(f"/v1/parent/events/{event_id}", params={"child_id": "child-1"}, headers=PARENT)
    assert client.get(url, params={"child_id": "child-1", "age": 7}, headers=CHILD).json()["story"] is None


def test_story_waits_until_1900_local_time():
    clock = [datetime(2026, 10, 11, 10, 59, tzinfo=timezone.utc)]
    client = make_client(clock)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    url = "/v1/child/story/today"
    assert client.get(url, params={"child_id": "child-1", "age": 7}, headers=CHILD).json()["status"] == "pending_evening"
    clock[0] = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    assert client.get(url, params={"child_id": "child-1", "age": 7}, headers=CHILD).json()["story"] is not None


def test_story_chat_session_turns_and_stop():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    body = {"child_id": "child-1", "story_id": STORY_ID, "text": "她是不是讨厌我"}
    first = client.post("/v1/child/chat-turns", json=body, headers=CHILD).json()
    assert first["session_id"] and first["turn_number"] == 1
    assert "不知道" in first["reply_text"]
    session = first["session_id"]
    assert client.post("/v1/child/chat-turns", json={**body, "child_id": "another-child", "session_id": session}, headers=CHILD).status_code == 404
    replies = []
    for turn in range(2, 6):
        current = client.post("/v1/child/chat-turns", json={**body, "text": "我还想聊", "session_id": session}, headers=CHILD).json()
        assert current["turn_number"] == turn
        replies.append(current["reply_text"])
    assert len(set(replies[:3])) == 3
    final = client.post("/v1/child/chat-turns", json={**body, "text": "我还想聊", "session_id": session}, headers=CHILD).json()
    assert final["route"] == "stopped" and final["session_id"] is None


def test_help_request_ends_session_and_expired_session_rejected():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    body = {"child_id": "child-1", "story_id": STORY_ID, "text": "我害怕"}
    help_turn = client.post("/v1/child/chat-turns", json=body, headers=CHILD).json()
    assert help_turn["route"] == "support" and help_turn["session_id"] is None
    assert "大人" in help_turn["reply_text"]
    first = client.post("/v1/child/chat-turns", json={**body, "text": "我想聊聊"}, headers=CHILD).json()
    clock[0] = datetime(2026, 10, 11, 12, 21, tzinfo=timezone.utc)
    assert client.post("/v1/child/chat-turns", json={**body, "session_id": first["session_id"]}, headers=CHILD).status_code == 404


def test_voice_chat_asr_to_tts_without_persistent_chat_text():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    class FakeAsr:
        def transcribe(self, audio, *, mime_type):
            assert mime_type == "audio/wav"
            return "她是不是讨厌我"
    class FakeTts:
        def synthesize(self, text):
            assert "不知道" in text
            return b"fake-mp3-data"
    service = SceneService(now=lambda: clock[0])
    service.submit_synthetic(**SAMPLE)
    client = TestClient(create_app(service, asr_provider=FakeAsr(), tts_provider=FakeTts(), synthetic_enabled=True))
    wav = io.BytesIO()
    with wave.open(wav, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(b"\xe8\x03" * 8000)
    headers = {**CHILD, "X-Child-ID": "child-1", "Content-Type": "audio/wav"}
    result = client.post("/v1/child/chat-turns/audio", content=wav.getvalue(), headers=headers)
    assert result.status_code == 200
    body = result.json()
    assert body["heard_text"] == "她是不是讨厌我"
    assert base64.b64decode(body["reply_audio_base64"]) == b"fake-mp3-data"
    assert body["tts_status"] == "ready"
    assert len(service._segments) == 1  # voice chat does not create a parent input
    story_audio = client.get("/v1/child/story/today/audio", params={"child_id": "child-1", "age": 7}, headers=CHILD)
    assert story_audio.status_code == 200 and story_audio.headers["content-type"] == "audio/mpeg"


def test_openai_tts_request_shape_without_external_call():
    def respond(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v1/audio/speech"
        assert request.read().decode().find("gpt-4o-mini-tts") >= 0
        return httpx.Response(200, content=b"fake-mp3-data", headers={"content-type": "audio/mpeg"})
    provider = OpenAITts("test-key", client=httpx.Client(transport=httpx.MockTransport(respond)))
    assert provider.synthesize("你好") == b"fake-mp3-data"


def test_parent_profile_binding_pause_and_mode_scope():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    headers = {**DEVICE, "X-Device-ID": "device-1", "X-Segment-ID": "new-1", "Content-Type": "audio/wav"}
    assert client.post("/v1/device/segments", content=b"bad", headers=headers).status_code == 403
    assert client.get("/v1/parent/profile", headers=CHILD).status_code == 403
    configure_local_device(client)
    profile = client.get("/v1/parent/profile", headers=PARENT).json()
    assert profile["listening_start"] == "08:00"
    assert profile["scheduled_listening_status"] == "configuration_only"
    assert client.get("/v1/child/story/today", params={"child_id": "child-1"}, headers=CHILD).status_code == 200
    assert client.get("/v1/child/story/today", params={"child_id": "another-child"}, headers=CHILD).status_code == 403
    assert client.get("/v1/parent/inputs", params={"child_id": "another-child", "date": "2026-10-11"}, headers=PARENT).status_code == 403
    assert client.put("/v1/parent/button-recording", json={"child_id": "child-1", "enabled": False}, headers=PARENT).status_code == 200
    assert client.post("/v1/device/segments", content=b"bad", headers=headers).status_code == 403
    assert client.put("/v1/parent/profile", json={"child_id": "another-child", "age": 8, "school_stage": "grade_2"}, headers=PARENT).status_code == 422


def test_local_profile_persists_and_age_is_server_owned(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    client = TestClient(create_app(service, synthetic_enabled=True))
    configure_local_device(client)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    service._store.close()
    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    reopened_client = TestClient(create_app(reopened, synthetic_enabled=True))
    profile = reopened_client.get("/v1/parent/profile", headers=PARENT).json()
    assert profile["device_id"] == "device-1" and profile["button_recording_enabled"] is True
    story = reopened_client.get("/v1/child/story/today", params={"child_id": "child-1", "age": 12}, headers=CHILD).json()["story"]
    assert story["age_band"] == "5-7"  # request cannot override the parent-set age
    reopened._store.close()


def test_parent_transcript_correction_recomputes_report_and_story(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    client = TestClient(create_app(service, synthetic_enabled=True))
    configure_local_device(client)
    first = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE).json()
    assert first["transcript_revision"] == 0
    report_url = "/v1/parent/reports/daily"
    params = {"child_id": "child-1", "date": "2026-10-11"}
    story_params = {"child_id": "child-1"}
    assert client.get(report_url, params=params, headers=PARENT).json()["event_count"] == 1
    assert client.get("/v1/child/story/today", params=story_params, headers=CHILD).json()["story"] is not None

    input_url = "/v1/parent/inputs/device-1/seg-1"
    correction = {"child_id": "child-1", "text": "今天我吃了苹果", "expected_revision": 0}
    changed = client.patch(input_url, json=correction, headers=PARENT)
    assert changed.status_code == 200
    assert changed.json()["status"] == "unclassified" and changed.json()["transcript_revision"] == 1
    assert client.patch(input_url, json=correction, headers=PARENT).status_code == 409
    report = client.get(report_url, params=params, headers=PARENT).json()
    assert report["event_count"] == 0 and report["revision"] == 2
    assert client.get("/v1/child/story/today", params=story_params, headers=CHILD).json()["story"] is None

    correction = {"child_id": "child-1", "text": SAMPLE["text"], "expected_revision": 1}
    restored = client.patch(input_url, json=correction, headers=PARENT).json()
    assert restored["status"] == "understood" and restored["transcript_revision"] == 2
    assert client.get(report_url, params=params, headers=PARENT).json()["event_count"] == 1
    assert client.get("/v1/child/story/today", params=story_params, headers=CHILD).json()["story"] is not None

    deleted = client.delete(input_url, params={"child_id": "child-1", "expected_revision": 2}, headers=PARENT)
    assert deleted.status_code == 200 and deleted.json()["status"] == "deleted"
    assert client.get("/v1/parent/inputs", params=params, headers=PARENT).json()["items"] == []
    assert client.get(report_url, params=params, headers=PARENT).json()["event_count"] == 0
    service._store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT transcript FROM segments").fetchone()[0] is None
    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    assert reopened.report(child_id="child-1", day=datetime(2026, 10, 11).date())["event_count"] == 0
    reopened._store.close()


def test_transcript_correction_expires_at_local_midnight(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0], sqlite_path=str(tmp_path / "scene.sqlite3"))
    client = TestClient(create_app(service, synthetic_enabled=True))
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)
    clock[0] = datetime(2026, 10, 11, 16, 1, tzinfo=timezone.utc)
    changed = client.patch("/v1/parent/inputs/device-1/seg-1", json={
        "child_id": "child-1", "text": "今天我吃了苹果", "expected_revision": 0,
    }, headers=PARENT)
    assert changed.status_code == 410
    inputs = client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()
    assert inputs["items"][0]["transcript"] is None
    assert client.get("/v1/parent/reports/daily", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()["event_count"] == 1
    service._store.close()


def test_old_local_sqlite_schema_migrates_transcript_revision(tmp_path):
    path = tmp_path / "scene.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("""CREATE TABLE segments (
            device_id TEXT NOT NULL, segment_id TEXT NOT NULL,
            child_id TEXT NOT NULL, received_at TEXT NOT NULL,
            local_date TEXT NOT NULL, expires_at TEXT NOT NULL,
            transcript TEXT, status TEXT NOT NULL, event_id TEXT,
            PRIMARY KEY(device_id, segment_id))""")
    service = SceneService(now=lambda: datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc), sqlite_path=str(path))
    assert service.submit_synthetic(**SAMPLE)["transcript_revision"] == 0
    service._store.close()
    with sqlite3.connect(path) as db:
        assert "transcript_revision" in {row[1] for row in db.execute("PRAGMA table_info(segments)")}


def test_unclassified_input_can_be_deleted_after_midnight(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    client = TestClient(create_app(service, synthetic_enabled=True))
    sample = {**SAMPLE, "text": "今天我吃了苹果"}
    assert client.post("/v1/dev/segments/text", json=sample, headers=DEVICE).json()["status"] == "unclassified"
    clock[0] = datetime(2026, 10, 11, 16, 1, tzinfo=timezone.utc)
    result = client.delete(
        "/v1/parent/inputs/device-1/seg-1",
        params={"child_id": "child-1", "expected_revision": 0}, headers=PARENT,
    )
    assert result.status_code == 200 and result.json()["status"] == "deleted"
    assert client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()["items"] == []
    service._store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT transcript FROM segments").fetchone()[0] is None


def test_parent_today_updates_with_report_and_corrections():
    clock = [datetime(2026, 10, 11, 10, 59, tzinfo=timezone.utc)]
    client = make_client(clock)
    event_id = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE).json()["event_id"]
    before = client.get("/v1/parent/today", params={"child_id": "child-1"}, headers=PARENT).json()
    assert before["active_input_count"] == 1
    assert before["peer_event_count"] == 1
    assert before["report_status"] == "pending"
    assert "notification" not in str(before).lower()
    assert client.get("/v1/parent/today", params={"child_id": "child-1"}, headers=CHILD).status_code == 403

    clock[0] = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    assert client.app.state.service.generate_due_reports() == 1
    after = client.get("/v1/parent/today", params={"child_id": "child-1"}, headers=PARENT).json()
    assert after["report_status"] == "ready" and after["report_revision"] == 1
    assert after["coverage_note"]
    assert client.get("/v1/parent/notifications", params={"child_id": "child-1"}, headers=PARENT).status_code == 404

    client.delete(f"/v1/parent/events/{event_id}", params={"child_id": "child-1"}, headers=PARENT)
    revised = client.get("/v1/parent/today", params={"child_id": "child-1"}, headers=PARENT).json()
    assert revised["active_input_count"] == 0
    assert revised["peer_event_count"] == 0
    assert revised["report_status"] == "insufficient"
    assert revised["report_revision"] == 2


def test_legacy_notification_table_removed_on_open(tmp_path):
    path = tmp_path / "scene.sqlite3"
    with sqlite3.connect(path) as db:
        db.execute("CREATE TABLE report_notifications (notification_id TEXT PRIMARY KEY)")
        db.execute("INSERT INTO report_notifications VALUES ('old')")
    service = SceneService(now=lambda: datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc), sqlite_path=str(path))
    service._store.close()
    with sqlite3.connect(path) as db:
        assert db.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='report_notifications'").fetchone() is None


def test_peer_scene_recognizes_common_phrasings_without_inventing_feelings():
    examples = [
        ("今天为什么甜甜不跟我玩儿，去跟裙裙玩儿了", "peer_changed_playmate", None),
        ("小明今天不陪我玩了，我觉得很难过", "not_playing_together", "难过"),
        ("同学不让我加入游戏，我很生气", "not_playing_together", "生气"),
        ("我想加入小朋友的游戏，可以吗", "wants_to_join_play", None),
    ]
    for phrase, situation, feeling in examples:
        event = extract_sample_event(phrase)
        assert event is not None and event["situation"] == situation
        assert event["explicit_feeling"] == feeling
        assert all(name not in str(event) for name in ("甜甜", "裙裙", "小明"))
    for unrelated in ("我想奶奶了", "朋友今天生病没来", "我今天很难过", "老师让我去玩积木", "小朋友去跟朋友玩了"):
        assert extract_sample_event(unrelated) is None


def test_daily_report_cites_each_observation_and_only_explicit_feelings():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    client = make_client(clock)
    first = client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE).json()
    second = client.post("/v1/dev/segments/text", json={**SAMPLE, "segment_id": "seg-2", "text": "小明今天不陪我玩了，我觉得很难过"}, headers=DEVICE).json()
    report = client.get("/v1/parent/reports/daily", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()
    assert report["event_count"] == 2
    assert len(report["observations"]) == 3
    assert {item["event_ids"][0] for item in report["observations"]} == {first["event_id"], second["event_id"]}
    assert [item for item in report["observations"] if "难过" in item["text"]] == [
        {"text": "这条留言明确提到自己感到难过。", "event_ids": [second["event_id"]]}
    ]
    assert "甜甜" not in str(report) and "小明" not in str(report)
    assert any("全天" in item for item in report["unknowns"])


def make_test_wav(sample: int, frames: int = 8000) -> bytes:
    data = io.BytesIO()
    with wave.open(data, "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(16000)
        out.writeframes(sample.to_bytes(2, "little", signed=True) * frames)
    return data.getvalue()


def test_device_silence_is_recorded_unreadable_without_asr_or_event(tmp_path):
    class FakeAsr:
        calls = 0
        def transcribe(self, audio, *, mime_type):
            self.calls += 1
            return SAMPLE["text"]

    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    store = tmp_path / "scene.sqlite3"
    asr = FakeAsr()
    service = SceneService(now=lambda: clock[0], sqlite_path=str(store))
    client = TestClient(create_app(service, asr_provider=asr))
    configure_local_device(client)
    headers = {**DEVICE, "X-Device-ID": "device-1", "X-Segment-ID": "silent-1", "Content-Type": "audio/wav"}
    silence = make_test_wav(0)
    first = client.post("/v1/device/segments", content=silence, headers=headers)
    assert first.status_code == 200
    assert first.json() == {"segment_id": "silent-1", "status": "unreadable", "event_id": None,
                            "transcript": None, "transcript_revision": 0}
    assert client.post("/v1/device/segments", content=silence, headers=headers).json() == first.json()
    assert asr.calls == 0
    assert client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()["items"][0]["status"] == "unreadable"
    assert client.get("/v1/parent/reports/daily", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()["status"] == "insufficient"
    service._store.close()
    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(store))
    assert reopened.inputs(child_id="child-1", day=datetime(2026, 10, 11).date())[0]["status"] == "unreadable"
    reopened._store.close()


def test_audio_quality_gate_rejects_short_and_incomplete_wav_without_asr():
    class FakeAsr:
        calls = 0
        def transcribe(self, audio, *, mime_type):
            self.calls += 1
            return SAMPLE["text"]

    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    asr = FakeAsr()
    service = SceneService(now=lambda: clock[0])
    service.submit_synthetic(**SAMPLE)
    client = TestClient(create_app(service, asr_provider=asr, tts_provider=object(), synthetic_enabled=True))
    configure_local_device(client)
    device_headers = {**DEVICE, "X-Device-ID": "device-1", "X-Segment-ID": "bad-1", "Content-Type": "audio/wav"}
    child_headers = {**CHILD, "X-Child-ID": "child-1", "Content-Type": "audio/wav"}
    for invalid in (make_test_wav(1000, 1600), make_test_wav(1000)[:-100]):
        assert client.post("/v1/device/segments", content=invalid, headers=device_headers).status_code == 422
        assert client.post("/v1/child/chat-turns/audio", content=invalid, headers=child_headers).status_code == 422
    assert client.post("/v1/child/chat-turns/audio", content=make_test_wav(0), headers=child_headers).status_code == 422
    assert asr.calls == 0
    assert ("device-1", "bad-1") not in service._segments


def test_report_coverage_revises_for_unclassified_and_unreadable_inputs(tmp_path):
    class FailIfCalledAsr:
        def transcribe(self, audio, *, mime_type):
            raise AssertionError("digital silence must not reach ASR")

    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    service.submit_synthetic(**SAMPLE)
    day = datetime(2026, 10, 11).date()
    first = service.report(child_id="child-1", day=day)
    assert first["revision"] == 1 and first["input_counts"]["input_count"] == 1

    service.submit_synthetic(**{**SAMPLE, "segment_id": "unrelated-1", "text": "今天我吃了苹果"})
    second = service.report(child_id="child-1", day=day)
    assert second["revision"] == 2 and second["event_count"] == 1
    assert second["input_counts"] == {"input_count": 2, "unreadable_count": 0,
                                      "unclassified_count": 1, "understood_count": 1}
    assert "未归入同伴相处" in second["coverage_note"]

    unreadable = service.submit_audio(child_id="child-1", device_id="device-1", segment_id="silent-1",
                                      wav_data=make_test_wav(0), asr=FailIfCalledAsr())
    assert unreadable["status"] == "unreadable"
    third = service.report(child_id="child-1", day=day)
    assert third["revision"] == 3 and third["event_count"] == 1
    assert third["input_counts"]["unreadable_count"] == 1
    assert "未听清" in third["coverage_note"]
    client = TestClient(create_app(service))
    overview = client.get("/v1/parent/today", params={"child_id": "child-1"}, headers=PARENT).json()
    assert overview["active_input_count"] == 3
    assert overview["unreadable_input_count"] == 1
    assert overview["unclassified_input_count"] == 1
    service._store.close()

    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    assert reopened.report(child_id="child-1", day=day) == third
    reopened.delete_input(child_id="child-1", device_id="device-1", segment_id="silent-1", expected_revision=0)
    revised = reopened.report(child_id="child-1", day=day)
    assert revised["revision"] == 4 and revised["input_counts"]["unreadable_count"] == 0
    reopened._store.close()


def test_old_cached_report_is_rebuilt_with_coverage_fields(tmp_path):
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    path = tmp_path / "scene.sqlite3"
    service = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    service.submit_synthetic(**SAMPLE)
    day = datetime(2026, 10, 11).date()
    service.report(child_id="child-1", day=day)
    service._store.close()
    with sqlite3.connect(path) as db:
        db.execute("UPDATE reports SET data=?", ('{"date":"2026-10-11","status":"ready","revision":1,"event_count":1}',))
    reopened = SceneService(now=lambda: clock[0], sqlite_path=str(path))
    rebuilt = reopened.report(child_id="child-1", day=day)
    assert rebuilt["report_schema_version"] == 2
    assert rebuilt["input_counts"]["input_count"] == 1
    reopened._store.close()


def test_unreadable_only_day_materializes_insufficient_report_at_1900(tmp_path):
    class FailIfCalledAsr:
        def transcribe(self, audio, *, mime_type):
            raise AssertionError("digital silence must not reach ASR")

    clock = [datetime(2026, 10, 11, 10, 59, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0], sqlite_path=str(tmp_path / "scene.sqlite3"))
    service.submit_audio(child_id="child-1", device_id="device-1", segment_id="silent-1",
                         wav_data=make_test_wav(0), asr=FailIfCalledAsr())
    assert service.generate_due_reports() == 0
    clock[0] = datetime(2026, 10, 11, 11, 0, tzinfo=timezone.utc)
    assert service.generate_due_reports() == 1
    report = service.report(child_id="child-1", day=datetime(2026, 10, 11).date())
    assert report["status"] == "insufficient" and report["event_count"] == 0
    assert report["input_counts"]["unreadable_count"] == 1
    assert "未听清" in report["coverage_note"]
    assert service.generate_due_reports() == 0
    service._store.close()


def test_child_story_narration_opening_and_voice_chat_flow():
    class FakeAsr:
        answers = iter(["米米好像我，我也想问问朋友", "我不想聊了"])
        def transcribe(self, audio, *, mime_type):
            assert mime_type == "audio/wav"
            return next(self.answers)

    class FakeTts:
        spoken = []
        def synthesize(self, text):
            self.spoken.append(text)
            return ("mp3:" + text).encode()

    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0])
    tts = FakeTts()
    client = TestClient(create_app(service, synthetic_enabled=True, asr_provider=FakeAsr(), tts_provider=tts))
    configure_local_device(client)
    client.put("/v1/parent/profile", json={"child_id": "child-1", "age": 9, "school_stage": "grade_3"}, headers=PARENT)
    client.post("/v1/dev/segments/text", json=SAMPLE, headers=DEVICE)

    story = client.get("/v1/child/story/today", params={"child_id": "child-1"}, headers=CHILD).json()["story"]
    assert story["age_band"] == "8-10"
    narration = client.get("/v1/child/story/today/audio", params={"child_id": "child-1"}, headers=CHILD)
    assert narration.status_code == 200 and narration.content == ("mp3:" + story["title"] + "。" + story["text"]).encode()
    assert narration.headers["x-ai-generated-voice"] == "true"

    opened = client.post("/v1/child/story-sessions", json={"child_id": "child-1", "story_id": STORY_ID}, headers=CHILD)
    assert opened.status_code == 200
    session = opened.json()
    assert session["age_band"] == "8-10" and session["opening_question"] == story["opening_question"]
    assert base64.b64decode(session["opening_audio_base64"]) == ("mp3:" + story["opening_question"]).encode()
    assert session["ai_voice_disclosure"]

    headers = {**CHILD, "X-Child-ID": "child-1", "X-Story-ID": STORY_ID,
               "X-Session-ID": session["session_id"], "Content-Type": "audio/wav"}
    first = client.post("/v1/child/chat-turns/audio", content=make_test_wav(1000), headers=headers).json()
    assert first["turn_number"] == 1 and first["session_id"] == session["session_id"]
    assert "米米" in first["reply_text"] and "朋友" in first["reply_text"]
    assert first["tts_status"] == "ready" and base64.b64decode(first["reply_audio_base64"]).startswith(b"mp3:")
    second = client.post("/v1/child/chat-turns/audio", content=make_test_wav(1000), headers=headers).json()
    assert second["route"] == "stopped" and second["session_id"] is None
    assert client.delete(f"/v1/child/story-sessions/{session['session_id']}", params={"child_id": "child-1"}, headers=CHILD).status_code == 404
    assert client.get("/v1/parent/inputs", params={"child_id": "child-1", "date": "2026-10-11"}, headers=PARENT).json()["items"][0]["transcript"] == SAMPLE["text"]
    assert len(service._segments) == 1  # Child chat audio/text is not saved as a parent input.


def test_child_story_session_tts_failure_and_explicit_stop():
    from companion_backend.providers import TtsError

    class FailingTts:
        def synthesize(self, text):
            raise TtsError("provider unavailable")

    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0])
    service.submit_synthetic(**SAMPLE)
    client = TestClient(create_app(service, synthetic_enabled=True, tts_provider=FailingTts()))
    assert client.post("/v1/child/story-sessions", json={"child_id": "child-1", "story_id": STORY_ID}, headers=CHILD).status_code == 422
    opened = client.post("/v1/child/story-sessions", json={"child_id": "child-1", "story_id": STORY_ID, "age": 7}, headers=CHILD).json()
    assert opened["tts_status"] == "failed" and opened["opening_audio_base64"] is None
    assert opened["opening_question"]
    assert client.delete(f"/v1/child/story-sessions/{opened['session_id']}", params={"child_id": "wrong-child"}, headers=CHILD).status_code == 404
    assert client.delete(f"/v1/child/story-sessions/{opened['session_id']}", params={"child_id": "child-1"}, headers=CHILD).json()["status"] == "stopped"
    assert client.post("/v1/child/chat-turns", json={"child_id": "child-1", "story_id": STORY_ID, "session_id": opened["session_id"], "text": "我还想说"}, headers=CHILD).status_code == 404


def test_child_story_session_expires_and_unavailable_story_cannot_continue():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0])
    event_id = service.submit_synthetic(**SAMPLE)["event_id"]
    client = TestClient(create_app(service, synthetic_enabled=True))
    start = {"child_id": "child-1", "story_id": STORY_ID, "age": 7}
    first = client.post("/v1/child/story-sessions", json=start, headers=CHILD).json()
    assert first["tts_status"] == "not_configured"
    service.revise_event(child_id="child-1", event_id=event_id, delete=True)
    assert client.post("/v1/child/chat-turns", json={**start, "text": "我想继续", "session_id": first["session_id"]}, headers=CHILD).status_code == 404
    assert client.post("/v1/child/story-sessions", json=start, headers=CHILD).status_code == 404
    assert client.delete(f"/v1/child/story-sessions/{first['session_id']}", params={"child_id": "child-1"}, headers=CHILD).status_code == 200

    service.submit_synthetic(**{**SAMPLE, "segment_id": "seg-2"})
    second = client.post("/v1/child/story-sessions", json=start, headers=CHILD).json()
    clock[0] = datetime(2026, 10, 11, 12, 21, tzinfo=timezone.utc)
    service.purge_expired()
    assert second["session_id"] not in service._chat_sessions
    assert client.delete(f"/v1/child/story-sessions/{second['session_id']}", params={"child_id": "child-1"}, headers=CHILD).status_code == 404


def test_child_help_and_stop_in_same_turn_ends_session_with_support():
    clock = [datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)]
    service = SceneService(now=lambda: clock[0])
    service.submit_synthetic(**SAMPLE)
    client = TestClient(create_app(service, synthetic_enabled=True))
    opened = client.post("/v1/child/story-sessions", json={"child_id": "child-1", "story_id": STORY_ID, "age": 7}, headers=CHILD).json()
    result = client.post("/v1/child/chat-turns", json={"child_id": "child-1", "story_id": STORY_ID,
        "session_id": opened["session_id"], "text": "他们打我了，我不想聊了"}, headers=CHILD).json()
    assert result["route"] == "support" and result["session_id"] is None
    assert "大人" in result["reply_text"]
