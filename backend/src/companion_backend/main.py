"""Local-only API scaffold. Do not expose to real users or the internet."""

from __future__ import annotations

import os
import asyncio
import base64
from contextlib import asynccontextmanager, suppress
from datetime import date, time
from hmac import compare_digest
from pathlib import Path
from typing import Literal

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field
from starlette.concurrency import run_in_threadpool

from .providers import AsrError, AsrProvider, TtsError, TtsProvider
from .deepseek_chat import ChatError, ChatProvider, DeepSeekV4
from .volc_speech import VolcAsr2, VolcTts2, DEFAULT_SPEAKER
from .audio import inspect_wav
from .service import SceneService, SegmentConflict, TranscriptExpired
from .stories import STORY_ID


class SyntheticSegment(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=64)
    segment_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)


class SegmentResult(BaseModel):
    segment_id: str
    status: str
    event_id: str | None
    transcript: str | None
    transcript_revision: int


class ParentInput(SegmentResult):
    received_at: str
    summary: str | None


class ParentInputsResponse(BaseModel):
    items: list[ParentInput]


class ParentToday(BaseModel):
    date: str
    active_input_count: int
    unreadable_input_count: int
    unclassified_input_count: int
    peer_event_count: int
    report_status: str
    report_revision: int
    coverage_note: str


class ReportInputCounts(BaseModel):
    input_count: int
    understood_count: int
    unclassified_count: int
    unreadable_count: int


class ReportObservation(BaseModel):
    text: str
    event_ids: list[str]


class PendingDailyReport(BaseModel):
    date: str
    status: Literal["pending"]
    revision: int


class FinishedDailyReport(BaseModel):
    date: str
    status: Literal["ready", "insufficient"]
    revision: int
    report_schema_version: int
    observations: list[ReportObservation]
    unknowns: list[str]
    parent_prompts: list[str]
    story_topic: str | None
    event_count: int
    input_counts: ReportInputCounts
    coverage_note: str


class EventRevision(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=300)


class TranscriptCorrection(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=500)
    expected_revision: int = Field(ge=0)


class ChatTurn(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    story_id: str = Field(min_length=1, max_length=64)
    text: str = Field(min_length=1, max_length=300)
    session_id: str | None = Field(default=None, max_length=64)


class StorySessionStart(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    story_id: str = Field(min_length=1, max_length=64)
    age: int | None = Field(default=None, ge=5, le=12)


class StorySessionResult(BaseModel):
    session_id: str
    story_id: str
    age_band: str
    opening_question: str
    expires_at: str
    tts_status: Literal["ready", "failed", "not_configured"]
    opening_audio_base64: str | None
    audio_mime_type: str | None
    ai_voice_disclosure: str | None


class ChildChatResult(BaseModel):
    session_id: str | None
    turn_number: int
    route: Literal["conversation", "stopped", "support"]
    reply_text: str
    reply_id: str
    tts_status: Literal["not_configured", "pending", "ready", "failed"]


class ChildTranscriptionResult(BaseModel):
    heard_text: str


class StoryNarrationRequest(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    story_id: Literal["friendship-bear", "s1", "s2", "s3", "s4", "s5", "s6"]
    page: int = Field(ge=0, le=20)
    text: str = Field(min_length=1, max_length=1500)


class ChildVoiceChatResult(ChildChatResult):
    heard_text: str
    reply_audio_base64: str | None
    audio_mime_type: str | None
    ai_voice_disclosure: str | None


class ChildProfileInput(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    age: int = Field(ge=5, le=12)
    school_stage: Literal[
        "kindergarten_large", "grade_1", "grade_2", "grade_3",
        "grade_4", "grade_5", "grade_6",
    ]
    listening_start: time | None = None
    listening_end: time | None = None


class DeviceBinding(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    device_id: str = Field(min_length=1, max_length=64)


class ButtonRecordingSetting(BaseModel):
    child_id: str = Field(min_length=1, max_length=64)
    enabled: bool


class ChildProfileResult(BaseModel):
    child_id: str
    age: int
    school_stage: str
    listening_start: str | None
    listening_end: str | None
    scheduled_listening_status: Literal["configuration_only"]
    button_recording_enabled: bool
    device_id: str | None


def validate_child_wav(data: bytes) -> None:
    if not inspect_wav(data, max_seconds=15):
        raise ValueError("Audio is digitally silent")


def create_app(
    service: SceneService | None = None, *, synthetic_enabled: bool | None = None,
    asr_provider: AsrProvider | None = None,
    tts_provider: TtsProvider | None = None,
    chat_provider: ChatProvider | None = None,
) -> FastAPI:
    if os.getenv("APP_ENV") != "local":
        raise RuntimeError("Production authentication, storage, and providers are not implemented")

    @asynccontextmanager
    async def lifespan(active_app: FastAPI):
        async def maintain():
            while True:
                await run_in_threadpool(active_app.state.service.purge_expired)
                await run_in_threadpool(active_app.state.service.generate_due_reports)
                await asyncio.sleep(60)

        task = asyncio.create_task(maintain())
        try:
            yield
        finally:
            task.cancel()
            with suppress(asyncio.CancelledError):
                await task

    app = FastAPI(title="Companion peer-scene scaffold", version="0.1.0", lifespan=lifespan)
    app.state.service = service or SceneService(sqlite_path=os.getenv("LOCAL_SQLITE_PATH"))
    api_key = os.getenv("VOLC_API_KEY", "")
    app.state.asr = asr_provider if asr_provider is not None else (
        VolcAsr2(api_key, resource_id=os.getenv("VOLC_ASR_RESOURCE_ID", "volc.seedasr.sauc.duration"))
        if api_key else None
    )
    app.state.tts = tts_provider if tts_provider is not None else (
        VolcTts2(api_key, speaker=os.getenv("VOLC_TTS_SPEAKER", DEFAULT_SPEAKER))
        if api_key else None
    )
    llm_key = os.getenv("DEEPSEEK_API_KEY", "")
    app.state.chat_model = chat_provider if chat_provider is not None else (
        DeepSeekV4(llm_key, model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-pro"))
        if llm_key else None
    )
    allowed = synthetic_enabled if synthetic_enabled is not None else os.getenv("ALLOW_SYNTHETIC_INPUT") == "1"

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        host = request.client.host if request.client else ""
        if host not in {"127.0.0.1", "::1", "testclient"}:
            return JSONResponse(status_code=403, content={"detail": "local-only scaffold"})
        return await call_next(request)

    def require_role(role: str):
        def check(authorization: str | None = Header(default=None)) -> None:
            expected = os.getenv(f"LOCAL_{role.upper()}_TOKEN", f"local-{role}-token")
            if role == "device" and os.getenv("LOCAL_DEVICE_TOKEN_FILE"):
                try:
                    expected = Path(os.environ["LOCAL_DEVICE_TOKEN_FILE"]).read_text().strip()
                except OSError:
                    raise HTTPException(status_code=503, detail="device token unavailable")
            actual = authorization.removeprefix("Bearer ") if authorization else ""
            if not compare_digest(actual, expected):
                raise HTTPException(status_code=403, detail="forbidden")
        return check

    parent = require_role("parent")
    child = require_role("child")
    device = require_role("device")

    def require_child_scope(child_id: str) -> None:
        try:
            app.state.service.assert_child_scope(child_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc

    @app.put("/v1/parent/profile", dependencies=[Depends(parent)], response_model=ChildProfileResult)
    def save_profile(body: ChildProfileInput):
        try:
            return app.state.service.set_profile(
                child_id=body.child_id, age=body.age, school_stage=body.school_stage,
                listening_start=body.listening_start.strftime("%H:%M") if body.listening_start else None,
                listening_end=body.listening_end.strftime("%H:%M") if body.listening_end else None,
            )
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/parent/profile", dependencies=[Depends(parent)], response_model=ChildProfileResult)
    def get_profile():
        profile = app.state.service.profile()
        if not profile:
            raise HTTPException(status_code=404, detail="child profile not configured")
        return profile

    @app.put("/v1/parent/device-binding", dependencies=[Depends(parent)], response_model=ChildProfileResult)
    def bind_device(body: DeviceBinding):
        require_child_scope(body.child_id)
        try:
            return app.state.service.bind_device(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.put("/v1/parent/button-recording", dependencies=[Depends(parent)], response_model=ChildProfileResult)
    def button_recording(body: ButtonRecordingSetting):
        require_child_scope(body.child_id)
        try:
            return app.state.service.set_button_recording(**body.model_dump())
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/healthz")
    def healthz():
        return {"status": "ok", "mode": "local_experiment", "asr_configured": app.state.asr is not None,
                "tts_configured": app.state.tts is not None, "chat_configured": app.state.chat_model is not None}

    @app.post("/v1/device/segments", dependencies=[Depends(device)], response_model=SegmentResult)
    async def device_audio(
        request: Request,
        x_device_id: str = Header(min_length=1, max_length=64),
        x_segment_id: str = Header(min_length=1, max_length=64),
    ):
        try:
            bound_child_id = app.state.service.authorize_device(x_device_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if app.state.asr is None:
            raise HTTPException(status_code=503, detail="ASR provider not configured")
        if request.headers.get("content-type", "").split(";", 1)[0] != "audio/wav":
            raise HTTPException(status_code=415, detail="audio/wav required")
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 220_000:
                raise HTTPException(status_code=413, detail="WAV exceeds 6-second prototype limit")
        try:
            return await run_in_threadpool(
                app.state.service.submit_audio,
                child_id=bound_child_id, device_id=x_device_id,
                segment_id=x_segment_id, wav_data=bytes(chunks), asr=app.state.asr,
            )
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AsrError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/v1/dev/segments/text", dependencies=[Depends(device)], response_model=SegmentResult)
    def submit_synthetic(body: SyntheticSegment):
        if not allowed:
            raise HTTPException(status_code=404, detail="not found")
        require_child_scope(body.child_id)
        try:
            return app.state.service.submit_synthetic(**body.model_dump())
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc

    @app.get("/v1/parent/inputs", dependencies=[Depends(parent)], response_model=ParentInputsResponse)
    def parent_inputs(child_id: str, day: date = Query(alias="date")):
        require_child_scope(child_id)
        return {"items": app.state.service.inputs(child_id=child_id, day=day)}

    @app.get("/v1/parent/today", dependencies=[Depends(parent)], response_model=ParentToday)
    def parent_today(child_id: str):
        require_child_scope(child_id)
        return app.state.service.parent_today(child_id=child_id)

    @app.patch("/v1/parent/inputs/{device_id}/{segment_id}", dependencies=[Depends(parent)], response_model=SegmentResult)
    def correct_parent_input(device_id: str, segment_id: str, body: TranscriptCorrection):
        require_child_scope(body.child_id)
        try:
            result = app.state.service.correct_transcript(
                child_id=body.child_id, device_id=device_id, segment_id=segment_id,
                text=body.text, expected_revision=body.expected_revision,
            )
        except TranscriptExpired as exc:
            raise HTTPException(status_code=410, detail=str(exc)) from exc
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="input not found")
        return result

    @app.delete("/v1/parent/inputs/{device_id}/{segment_id}", dependencies=[Depends(parent)], response_model=SegmentResult)
    def delete_parent_input(device_id: str, segment_id: str, child_id: str, expected_revision: int = Query(ge=0)):
        require_child_scope(child_id)
        try:
            result = app.state.service.delete_input(
                child_id=child_id, device_id=device_id, segment_id=segment_id,
                expected_revision=expected_revision,
            )
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if result is None:
            raise HTTPException(status_code=404, detail="input not found")
        return result

    @app.get("/v1/parent/reports/daily", dependencies=[Depends(parent)], response_model=PendingDailyReport | FinishedDailyReport)
    def daily_report(child_id: str, day: date = Query(alias="date")):
        require_child_scope(child_id)
        return app.state.service.report(child_id=child_id, day=day)

    @app.patch("/v1/parent/events/{event_id}", dependencies=[Depends(parent)])
    def revise_event(event_id: str, body: EventRevision):
        require_child_scope(body.child_id)
        result = app.state.service.revise_event(child_id=body.child_id, event_id=event_id, summary=body.summary)
        if result is None:
            raise HTTPException(status_code=404, detail="not found")
        return result

    @app.delete("/v1/parent/events/{event_id}", dependencies=[Depends(parent)])
    def delete_event(event_id: str, child_id: str):
        require_child_scope(child_id)
        result = app.state.service.revise_event(child_id=child_id, event_id=event_id, delete=True)
        if result is None:
            raise HTTPException(status_code=404, detail="not found")
        return {"status": "deleted", "event_id": event_id}

    @app.get("/v1/child/story/today", dependencies=[Depends(child)])
    def child_story(child_id: str, age: int | None = None):
        try:
            return app.state.service.story(child_id=child_id, age=app.state.service.child_age(child_id, age))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    @app.get("/v1/child/story/today/audio", dependencies=[Depends(child)])
    def child_story_audio(child_id: str, age: int | None = None):
        if app.state.tts is None:
            raise HTTPException(status_code=503, detail="TTS provider not configured")
        try:
            recommendation = app.state.service.story(child_id=child_id, age=app.state.service.child_age(child_id, age))
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        if recommendation["story"] is None:
            raise HTTPException(status_code=404, detail="no story recommendation today")
        try:
            story = recommendation["story"]
            audio = app.state.tts.synthesize(f"{story['title']}。{story['text']}")
        except TtsError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store", "X-AI-Generated-Voice": "true"})

    @app.post("/v1/child/story-sessions", dependencies=[Depends(child)], response_model=StorySessionResult)
    def start_story_session(body: StorySessionStart):
        try:
            session = app.state.service.start_story_session(**body.model_dump())
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            status = 422 if "age" in str(exc) else 404
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        base = {**session, "opening_audio_base64": None, "audio_mime_type": None, "ai_voice_disclosure": None}
        if app.state.tts is None:
            return {**base, "tts_status": "not_configured"}
        try:
            audio = app.state.tts.synthesize(session["opening_question"])
        except TtsError:
            return {**base, "tts_status": "failed"}
        return {**session, "tts_status": "ready", "opening_audio_base64": base64.b64encode(audio).decode("ascii"),
                "audio_mime_type": "audio/mpeg", "ai_voice_disclosure": "这段声音由 AI 生成。"}

    @app.delete("/v1/child/story-sessions/{session_id}", dependencies=[Depends(child)])
    def stop_story_session(session_id: str, child_id: str):
        try:
            stopped = app.state.service.stop_story_session(child_id=child_id, session_id=session_id)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        if not stopped:
            raise HTTPException(status_code=404, detail="story session not found")
        return {"status": "stopped", "session_id": session_id}

    @app.post("/v1/child/chat-turns", dependencies=[Depends(child)], response_model=ChildChatResult)
    def chat_turn(body: ChatTurn):
        if app.state.chat_model is None and not allowed:
            raise HTTPException(status_code=503, detail="LLM provider not configured")
        try:
            turn = app.state.service.chat(**body.model_dump(), model=app.state.chat_model)
            return {**turn, "tts_status": "pending" if app.state.tts else "not_configured"}
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ChatError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc

    @app.post("/v1/child/chat-turns/transcribe", dependencies=[Depends(child)], response_model=ChildTranscriptionResult)
    async def transcribe_child_turn(request: Request, x_child_id: str = Header(min_length=1, max_length=64)):
        require_child_scope(x_child_id)
        if app.state.asr is None:
            raise HTTPException(status_code=503, detail="ASR provider not configured")
        if request.headers.get("content-type", "").split(";", 1)[0] != "audio/wav":
            raise HTTPException(status_code=415, detail="audio/wav required")
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 500_000:
                raise HTTPException(status_code=413, detail="WAV exceeds 15-second prototype limit")
        try:
            validate_child_wav(bytes(chunks))
            heard = await run_in_threadpool(app.state.asr.transcribe, bytes(chunks), mime_type="audio/wav")
            return {"heard_text": heard}
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
        except AsrError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.post("/v1/child/chat-turns/{reply_id}/speech", dependencies=[Depends(child)])
    async def speak_child_turn(reply_id: str, child_id: str):
        if app.state.tts is None:
            raise HTTPException(status_code=503, detail="TTS provider not configured")
        require_child_scope(child_id)
        text = app.state.service.speech_reply(child_id=child_id, reply_id=reply_id)
        if text is None:
            raise HTTPException(status_code=404, detail="reply not found or expired")
        try:
            audio = await run_in_threadpool(app.state.tts.synthesize, text)
        except TtsError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store", "X-AI-Generated-Voice": "true"})

    @app.post("/v1/child/story-narration", dependencies=[Depends(child)])
    async def story_narration(body: StoryNarrationRequest):
        require_child_scope(body.child_id)
        if app.state.tts is None:
            raise HTTPException(status_code=503, detail="TTS provider not configured")
        try:
            audio = await run_in_threadpool(app.state.tts.synthesize, body.text)
        except TtsError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        return Response(audio, media_type="audio/mpeg", headers={"Cache-Control": "no-store", "X-AI-Generated-Voice": "true"})

    @app.post("/v1/child/chat-turns/audio", dependencies=[Depends(child)], response_model=ChildVoiceChatResult)
    async def chat_voice_turn(
        request: Request,
        x_child_id: str = Header(min_length=1, max_length=64),
        x_story_id: str = Header(default=STORY_ID, min_length=1, max_length=64),
        x_session_id: str | None = Header(default=None, max_length=64),
    ):
        if app.state.asr is None or app.state.tts is None or (app.state.chat_model is None and not allowed):
            raise HTTPException(status_code=503, detail="ASR, LLM and TTS providers required")
        if request.headers.get("content-type", "").split(";", 1)[0] != "audio/wav":
            raise HTTPException(status_code=415, detail="audio/wav required")
        chunks = bytearray()
        async for chunk in request.stream():
            chunks.extend(chunk)
            if len(chunks) > 500_000:
                raise HTTPException(status_code=413, detail="WAV exceeds 15-second prototype limit")

        def process() -> dict:
            validate_child_wav(bytes(chunks))
            heard = app.state.asr.transcribe(bytes(chunks), mime_type="audio/wav")
            turn = app.state.service.chat(
                child_id=x_child_id, story_id=x_story_id, text=heard, session_id=x_session_id,
                model=app.state.chat_model,
            )
            try:
                audio = app.state.tts.synthesize(turn["reply_text"])
            except TtsError:
                return {**turn, "heard_text": heard, "tts_status": "failed", "reply_audio_base64": None,
                        "audio_mime_type": None, "ai_voice_disclosure": None}
            return {**turn, "heard_text": heard, "tts_status": "ready",
                    "reply_audio_base64": base64.b64encode(audio).decode("ascii"),
                    "audio_mime_type": "audio/mpeg", "ai_voice_disclosure": "这段声音由 AI 生成。"}

        try:
            return await run_in_threadpool(process)
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except SegmentConflict as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        except ValueError as exc:
            status = 404 if "story" in str(exc) or "session" in str(exc) else 422
            raise HTTPException(status_code=status, detail=str(exc)) from exc
        except AsrError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc
        except ChatError as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    return app


app = create_app()
