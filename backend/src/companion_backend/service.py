"""Application service for the local peer-scene experiment."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta, timezone
from threading import RLock
from typing import Callable
from uuid import uuid4
from zoneinfo import ZoneInfo

from .graphs import CHAT_GRAPH, INGEST_GRAPH, REPORT_GRAPH
from .audio import inspect_wav
from .providers import AsrProvider
from .storage import SQLiteStore
from .stories import STORY_ID, STORY_TOPIC, STORY_VARIANTS, age_band
from .deepseek_chat import ChatProvider


class SegmentConflict(ValueError):
    """A device reused one segment ID for another child."""


class TranscriptExpired(ValueError):
    """An expired transcript cannot be recreated by a late correction."""


class SceneService:
    REPORT_SCHEMA_VERSION = 4

    def __init__(self, *, now: Callable[[], datetime] | None = None, family_timezone: str = "Asia/Shanghai", sqlite_path: str | None = None):
        self.now = now or (lambda: datetime.now(timezone.utc))
        self.zone = ZoneInfo(family_timezone)
        self._lock = RLock()
        self._segments: dict[tuple[str, str], dict] = {}
        self._events: dict[str, dict] = {}
        self._revision: dict[tuple[str, str], int] = {}
        self._report_cache: dict[tuple[str, str], dict] = {}
        self._chat_sessions: dict[str, dict] = {}
        self._speech_turns: dict[str, dict] = {}
        self._profile: dict | None = None
        self._store = SQLiteStore(sqlite_path) if sqlite_path else None
        if self._store:
            self._segments, self._events, self._revision = self._store.load()
            self._profile = self._store.load_profile()
            self.purge_expired()

    def profile(self) -> dict | None:
        with self._lock:
            return self._profile.copy() if self._profile else None

    def set_profile(self, *, child_id: str, age: int, school_stage: str, listening_start: str | None, listening_end: str | None) -> dict:
        if not 5 <= age <= 12:
            raise ValueError("age must be 5-12")
        if (listening_start is None) != (listening_end is None):
            raise ValueError("listening window requires both start and end")
        if listening_start == listening_end and listening_start is not None:
            raise ValueError("listening window cannot have equal start and end")
        with self._lock:
            if self._profile and self._profile["child_id"] != child_id:
                raise ValueError("local experiment supports one child profile")
            profile = {
                "child_id": child_id, "age": age, "school_stage": school_stage,
                "listening_start": listening_start, "listening_end": listening_end,
                "scheduled_listening_status": "configuration_only",
                "button_recording_enabled": self._profile["button_recording_enabled"] if self._profile else False,
                "device_id": self._profile["device_id"] if self._profile else None,
            }
            if self._store:
                self._store.save_profile(profile)
            self._profile = profile
            return profile.copy()

    def bind_device(self, *, child_id: str, device_id: str) -> dict:
        with self._lock:
            self.assert_child_scope(child_id)
            if not self._profile:
                raise ValueError("create child profile first")
            profile = {**self._profile, "device_id": device_id}
            if self._store:
                self._store.save_profile(profile)
            self._profile = profile
            return profile.copy()

    def set_button_recording(self, *, child_id: str, enabled: bool) -> dict:
        with self._lock:
            self.assert_child_scope(child_id)
            if not self._profile:
                raise ValueError("create child profile first")
            profile = {**self._profile, "button_recording_enabled": enabled}
            if self._store:
                self._store.save_profile(profile)
            self._profile = profile
            return profile.copy()

    def assert_child_scope(self, child_id: str) -> None:
        if self._profile and self._profile["child_id"] != child_id:
            raise PermissionError("child profile is outside this local family")

    def child_age(self, child_id: str, supplied_age: int | None) -> int:
        self.assert_child_scope(child_id)
        if self._profile:
            return self._profile["age"]
        if supplied_age is None:
            raise ValueError("age is required until a child profile exists")
        return supplied_age

    def authorize_device(self, device_id: str) -> str:
        with self._lock:
            profile = self._profile
            if not profile or profile["device_id"] != device_id or not profile["button_recording_enabled"]:
                raise PermissionError("device is unbound or button recording is paused")
            return profile["child_id"]

    def _local_now(self) -> datetime:
        return self.now().astimezone(self.zone)

    def submit_synthetic(self, *, child_id: str, device_id: str, segment_id: str, text: str) -> dict:
        key = (device_id, segment_id)
        with self._lock:
            if key in self._segments:
                existing = self._segments[key]
                if existing["child_id"] != child_id:
                    raise SegmentConflict("segment ID already belongs to another child")
                return self._segment_view(existing)
            local_now = self._local_now()
            expires = datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=self.zone)
            result = INGEST_GRAPH.invoke({"raw_text": text})
            event_data = result["event"]
            event_id = None
            event = None
            revision_key = (child_id, local_now.date().isoformat())
            revision = self._revision.get(revision_key, 0) + 1
            if event_data:
                event_id = uuid4().hex
                event = {
                    **event_data, "event_id": event_id, "child_id": child_id,
                    "source": "button", "local_date": local_now.date().isoformat(),
                    "segment_id": segment_id,
                }
            segment = {
                "device_id": device_id, "segment_id": segment_id, "child_id": child_id,
                "received_at": local_now.isoformat(), "local_date": local_now.date().isoformat(),
                "expires_at": expires, "transcript": result["transcript"],
                "status": "understood" if event_data else "unclassified", "event_id": event_id,
                "transcript_revision": 0,
            }
            if self._store:
                self._store.save(segment, event, revision)
            if event:
                self._events[event_id] = event
            self._revision[revision_key] = revision
            self._segments[key] = segment
            return self._segment_view(segment)

    def submit_audio(self, *, child_id: str, device_id: str, segment_id: str, wav_data: bytes, asr: AsrProvider) -> dict:
        if not 44 <= len(wav_data) <= 220_000:
            raise ValueError("WAV size outside 6-second prototype limits")
        has_signal = inspect_wav(wav_data, max_seconds=6)
        with self._lock:
            existing = self._segments.get((device_id, segment_id))
            if existing:
                if existing["child_id"] != child_id:
                    raise SegmentConflict("segment ID already belongs to another child")
                return self._segment_view(existing)
            if not has_signal:
                local_now = self._local_now()
                revision_key = (child_id, local_now.date().isoformat())
                revision = self._revision.get(revision_key, 0) + 1
                segment = {
                    "device_id": device_id, "segment_id": segment_id, "child_id": child_id,
                    "received_at": local_now.isoformat(), "local_date": local_now.date().isoformat(),
                    "expires_at": datetime.combine(local_now.date() + timedelta(days=1), time.min, tzinfo=self.zone),
                    "transcript": None, "status": "unreadable", "event_id": None,
                    "transcript_revision": 0,
                }
                if self._store:
                    self._store.save(segment, None, revision)
                self._segments[(device_id, segment_id)] = segment
                self._revision[revision_key] = revision
                return self._segment_view(segment)
            transcript = asr.transcribe(wav_data, mime_type="audio/wav")
            return self.submit_synthetic(
                child_id=child_id, device_id=device_id, segment_id=segment_id,
                text=transcript,
            )

    def _segment_view(self, segment: dict) -> dict:
        if self._local_now() >= segment["expires_at"]:
            # Local prototype: erase on read. Production also needs a scheduled
            # physical deletion job and backup/cache lifecycle controls.
            if segment["transcript"] is not None:
                if self._store:
                    self._store.erase_transcript(device_id=segment["device_id"], segment_id=segment["segment_id"])
                segment["transcript"] = None
        event_id = segment["event_id"]
        deleted = event_id is not None and self._events[event_id]["review_state"] == "deleted"
        if deleted:
            return {"segment_id": segment["segment_id"], "status": "deleted", "event_id": None,
                    "transcript": None, "transcript_revision": segment["transcript_revision"]}
        visible = self._local_now() < segment["expires_at"]
        return {
            "segment_id": segment["segment_id"], "status": segment["status"],
            "event_id": event_id, "transcript": segment["transcript"] if visible else None,
            "transcript_revision": segment["transcript_revision"],
        }

    def correct_transcript(self, *, child_id: str, device_id: str, segment_id: str, text: str, expected_revision: int) -> dict | None:
        with self._lock:
            segment = self._segments.get((device_id, segment_id))
            if segment is None or segment["child_id"] != child_id:
                return None
            if segment["status"] == "deleted" or (segment["event_id"] and self._events[segment["event_id"]]["review_state"] == "deleted"):
                raise SegmentConflict("deleted input cannot be corrected")
            if self._local_now() >= segment["expires_at"]:
                raise TranscriptExpired("same-day correction window has ended")
            if segment["transcript_revision"] != expected_revision:
                raise SegmentConflict("transcript revision has changed")
            result = INGEST_GRAPH.invoke({"raw_text": text})
            event_data = result["event"]
            old_event_id = segment["event_id"]
            changed_events = []
            if event_data:
                event_id = old_event_id or uuid4().hex
                event = {
                    **event_data, "event_id": event_id, "child_id": child_id,
                    "source": "button", "local_date": segment["local_date"],
                    "segment_id": segment_id, "review_state": "parent_corrected",
                }
                changed_events.append(event)
            else:
                event_id = None
                if old_event_id:
                    changed_events.append({**self._events[old_event_id], "review_state": "deleted"})
            changed_segment = {
                **segment, "transcript": result["transcript"],
                "status": "understood" if event_data else "unclassified",
                "event_id": event_id, "transcript_revision": expected_revision + 1,
            }
            revision_key = (child_id, segment["local_date"])
            revision = self._revision.get(revision_key, 0) + 1
            if self._store:
                self._store.save_segment_change(changed_segment, changed_events, revision)
            self._segments[(device_id, segment_id)] = changed_segment
            for event in changed_events:
                self._events[event["event_id"]] = event
            self._revision[revision_key] = revision
            return self._segment_view(changed_segment)

    def delete_input(self, *, child_id: str, device_id: str, segment_id: str, expected_revision: int) -> dict | None:
        with self._lock:
            segment = self._segments.get((device_id, segment_id))
            if segment is None or segment["child_id"] != child_id:
                return None
            if segment["transcript_revision"] != expected_revision:
                raise SegmentConflict("transcript revision has changed")
            if segment["status"] == "deleted":
                return self._segment_view(segment)
            changed_events = []
            if segment["event_id"]:
                changed_events.append({**self._events[segment["event_id"]], "review_state": "deleted"})
            changed_segment = {**segment, "status": "deleted", "transcript": None,
                               "transcript_revision": expected_revision + 1}
            revision_key = (child_id, segment["local_date"])
            revision = self._revision.get(revision_key, 0) + 1
            if self._store:
                self._store.save_segment_change(changed_segment, changed_events, revision)
            self._segments[(device_id, segment_id)] = changed_segment
            for event in changed_events:
                self._events[event["event_id"]] = event
            self._revision[revision_key] = revision
            return self._segment_view(changed_segment)

    def purge_expired(self) -> int:
        """Erase expired demo transcripts; safe to call from a future scheduler."""
        with self._lock:
            now = self._local_now()
            count = 0
            for segment in self._segments.values():
                if now >= segment["expires_at"] and segment["transcript"] is not None:
                    if self._store:
                        self._store.erase_transcript(device_id=segment["device_id"], segment_id=segment["segment_id"])
                    segment["transcript"] = None
                    count += 1
            for session_id, session in list(self._chat_sessions.items()):
                if session["expires_at"] <= now:
                    self._chat_sessions.pop(session_id, None)
            for reply_id, reply in list(self._speech_turns.items()):
                if reply["expires_at"] <= now:
                    self._speech_turns.pop(reply_id, None)
            return count

    def inputs(self, *, child_id: str, day: date) -> list[dict]:
        with self._lock:
            items = []
            for segment in self._segments.values():
                if segment["child_id"] != child_id or segment["local_date"] != day.isoformat():
                    continue
                view = self._segment_view(segment)
                if view["status"] == "deleted":
                    continue
                event = self._events.get(segment["event_id"])
                items.append({**view, "received_at": segment["received_at"], "summary": event["summary"] if event else None})
            return sorted(items, key=lambda item: item["received_at"])

    def _day_input_counts(self, *, child_id: str, day: date) -> dict[str, int]:
        counts = {"input_count": 0, "unreadable_count": 0, "unclassified_count": 0, "understood_count": 0}
        for segment in self._segments.values():
            if segment["child_id"] != child_id or segment["local_date"] != day.isoformat():
                continue
            status = self._segment_view(segment)["status"]
            if status == "deleted":
                continue
            counts["input_count"] += 1
            key = f"{status}_count"
            if key in counts:
                counts[key] += 1
        return counts

    def report(self, *, child_id: str, day: date) -> dict:
        with self._lock:
            self.assert_child_scope(child_id)
            local_now = self._local_now()
            if day > local_now.date():
                return {"date": day.isoformat(), "status": "pending", "revision": 0}
            revision = self._revision.get((child_id, day.isoformat()), 0)
            if self._store:
                cached = self._store.get_report(child_id=child_id, local_date=day.isoformat(), revision=revision)
                if cached is not None and cached.get("report_schema_version") == self.REPORT_SCHEMA_VERSION:
                    return cached
                if cached is not None:
                    return self._materialize_report(child_id=child_id, day=day, revision=revision)
            cached = self._report_cache.get((child_id, day.isoformat()))
            if cached is not None and cached["revision"] == revision:
                return cached
            if day == local_now.date() and local_now.time() < time(19, 0):
                return {"date": day.isoformat(), "status": "pending", "revision": 0}
            return self._materialize_report(child_id=child_id, day=day, revision=revision)

    def generate_report_now(self, *, child_id: str) -> dict:
        """Generate today's current revision on a parent request, regardless of time."""
        with self._lock:
            self.assert_child_scope(child_id)
            day = self._local_now().date()
            revision = self._revision.get((child_id, day.isoformat()), 0)
            return self._materialize_report(child_id=child_id, day=day, revision=revision)

    def _materialize_report(self, *, child_id: str, day: date, revision: int) -> dict:
        events = [e.copy() for e in self._events.values() if e["child_id"] == child_id and e["local_date"] == day.isoformat()]
        report = REPORT_GRAPH.invoke({"events": events, "input_counts": self._day_input_counts(child_id=child_id, day=day)})["report"]
        result = {"date": day.isoformat(), "revision": revision, "report_schema_version": self.REPORT_SCHEMA_VERSION, **report}
        if self._store:
            self._store.save_report(child_id=child_id, local_date=day.isoformat(), revision=revision, report=result)
        self._report_cache[(child_id, day.isoformat())] = result
        return result

    def parent_today(self, *, child_id: str) -> dict:
        with self._lock:
            day = self._local_now().date()
            counts = self._day_input_counts(child_id=child_id, day=day)
            report = self.report(child_id=child_id, day=day)
            return {
                "date": day.isoformat(), "active_input_count": counts["input_count"],
                "unreadable_input_count": counts["unreadable_count"],
                "unclassified_input_count": counts["unclassified_count"],
                "peer_event_count": report.get("event_count", 0) if report["status"] != "pending" else sum(
                    1 for event in self._events.values()
                    if event["child_id"] == child_id and event["local_date"] == day.isoformat()
                    and event["review_state"] != "deleted"
                ),
                "report_status": report["status"],
                "report_revision": report["revision"],
                "coverage_note": report.get("coverage_note", "仅基于娃娃按键留言，不能代表全天情况。"),
            }

    def generate_due_reports(self) -> int:
        """Materialize today's due reports and stale historical revisions."""
        with self._lock:
            keys = set(self._revision)
            generated = 0
            for child_id, day_string in keys:
                day = date.fromisoformat(day_string)
                if day > self._local_now().date() or (day == self._local_now().date() and self._local_now().time() < time(19, 0)):
                    continue
                revision = self._revision[(child_id, day_string)]
                if self._store:
                    cached = self._store.get_report(child_id=child_id, local_date=day_string, revision=revision)
                    if cached is not None and cached.get("report_schema_version") == self.REPORT_SCHEMA_VERSION:
                        continue
                self.report(child_id=child_id, day=day)
                generated += 1
            return generated

    def revise_event(self, *, child_id: str, event_id: str, summary: str | None = None, delete: bool = False) -> dict | None:
        with self._lock:
            event = self._events.get(event_id)
            if event is None or event["child_id"] != child_id:
                return None
            changed = event.copy()
            if delete:
                changed["review_state"] = "deleted"
            elif summary is not None:
                changed["summary"] = summary
                changed["review_state"] = "parent_corrected"
            key = (child_id, event["local_date"])
            revision = self._revision.get(key, 0) + 1
            if self._store:
                self._store.save_revision(changed, revision, erase_transcript=delete)
            self._events[event_id] = changed
            self._revision[key] = revision
            if delete:
                for segment in self._segments.values():
                    if segment["event_id"] == event_id:
                        segment["transcript"] = None
            return {k: v for k, v in changed.items() if k != "segment_id"}

    def story(self, *, child_id: str, age: int, day: date | None = None) -> dict:
        self.assert_child_scope(child_id)
        band = age_band(age)
        target_day = day or self._local_now().date()
        if target_day > self._local_now().date() or (target_day == self._local_now().date() and self._local_now().time() < time(19, 0)):
            return {"status": "pending_evening", "date": target_day.isoformat(), "story": None}
        with self._lock:
            eligible = any(
                event["child_id"] == child_id and event["local_date"] == target_day.isoformat()
                and event["topic"] == "peer_play" and event["review_state"] != "deleted"
                for event in self._events.values()
            )
        if not eligible:
            return {"status": "no_recommendation", "date": target_day.isoformat(), "story": None}
        return {
            "status": "draft_for_local_demo", "date": target_day.isoformat(),
            "story": {
                "id": STORY_ID, "topic": STORY_TOPIC, "age_band": band,
                **STORY_VARIANTS[band], "approved": False, "demo_only": True,
                "ai_voice_disclosure": "如播放合成配音：这段声音由 AI 生成。",
            },
        }

    def chat(self, *, child_id: str, text: str, story_id: str | None = None, session_id: str | None = None,
             model: ChatProvider | None = None) -> dict:
        text = text.strip()
        if not text or len(text) > 300:
            raise ValueError("chat text must be 1-300 characters")
        self.assert_child_scope(child_id)
        if story_id is not None and (story_id != STORY_ID or self.story(child_id=child_id, age=7)["story"] is None):
            raise ValueError("story is not available for this child today")
        with self._lock:
            now = self._local_now()
            existing_session = session_id is not None
            if session_id:
                session = self._chat_sessions.get(session_id)
                if not session or session["child_id"] != child_id or session["story_id"] != story_id or session["expires_at"] <= now:
                    raise ValueError("chat session not found or expired")
            else:
                session_id = uuid4().hex
                session = {"child_id": child_id, "story_id": story_id, "turns": 0,
                           "history": [], "expires_at": now + timedelta(minutes=20)}
            turn_number = session["turns"] + 1
            history = list(session.get("history", []))
            age = self._profile["age"] if self._profile else 7
            facts = [
                event["summary"] + (f"孩子明确说感到{event['explicit_feeling']}。" if event.get("explicit_feeling") else "")
                for event in self._events.values()
                if event["child_id"] == child_id and event["local_date"] == now.date().isoformat()
                and event["topic"] == "peer_play" and event["review_state"] != "deleted"
            ][:3]
        # Network model call stays outside the service lock; a failed call does not consume a turn.
        result = CHAT_GRAPH.invoke({"text": text, "turn_number": turn_number, "age": age,
                                    "daily_facts": facts, "history": history, "model": model,
                                    "story_context": story_id is not None})
        with self._lock:
            now = self._local_now()
            current = self._chat_sessions.get(session_id)
            if current and (current["turns"] != turn_number - 1 or current["expires_at"] <= now):
                raise SegmentConflict("chat session changed")
            if current is None and existing_session:
                raise ValueError("chat session not found or expired")
            if turn_number >= 6 and result["route"] == "conversation":
                result = {"route": "stopped", "reply": "我们今天先聊到这里。想继续时，可以找家长一起说说。"}
            if result["route"] in {"stopped", "support"}:
                self._chat_sessions.pop(session_id, None)
                next_session_id = None
            else:
                session["turns"] = turn_number
                session["expires_at"] = now + timedelta(minutes=20)
                session["history"] = (history + [
                    {"role": "user", "content": text},
                    {"role": "assistant", "content": result["reply"]},
                ])[-6:]
                self._chat_sessions[session_id] = session
                next_session_id = session_id
            reply_id = uuid4().hex
            self._speech_turns[reply_id] = {
                "child_id": child_id, "text": result["reply"],
                "expires_at": now + timedelta(minutes=20),
            }
            return {
                "session_id": next_session_id, "turn_number": turn_number,
                "route": result["route"], "reply_text": result["reply"],
                "reply_id": reply_id, "tts_status": "not_configured",
            }

    def speech_reply(self, *, child_id: str, reply_id: str) -> str | None:
        self.assert_child_scope(child_id)
        with self._lock:
            reply = self._speech_turns.get(reply_id)
            if not reply or reply["child_id"] != child_id or reply["expires_at"] <= self._local_now():
                return None
            return reply["text"]

    def start_story_session(self, *, child_id: str, story_id: str, age: int | None = None) -> dict:
        recommendation = self.story(child_id=child_id, age=self.child_age(child_id, age))
        story = recommendation["story"]
        if story is None or story["id"] != story_id:
            raise ValueError("story is not available for this child today")
        with self._lock:
            now = self._local_now()
            session_id = uuid4().hex
            self._chat_sessions[session_id] = {
                "child_id": child_id, "story_id": story_id,
                "turns": 0, "history": [], "expires_at": now + timedelta(minutes=20),
            }
            return {
                "session_id": session_id, "story_id": story_id,
                "age_band": story["age_band"],
                "opening_question": story["opening_question"],
                "expires_at": self._chat_sessions[session_id]["expires_at"].isoformat(),
            }

    def stop_story_session(self, *, child_id: str, session_id: str) -> bool:
        self.assert_child_scope(child_id)
        with self._lock:
            session = self._chat_sessions.get(session_id)
            if not session or session["child_id"] != child_id or session["expires_at"] <= self._local_now():
                return False
            self._chat_sessions.pop(session_id, None)
            return True
