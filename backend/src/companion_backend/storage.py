"""Local SQLite persistence for the adult-voice functional experiment.

This is deliberately not the production PostgreSQL/encrypted child-data store.
"""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from pathlib import Path


class SQLiteStore:
    def __init__(self, path: str):
        target = Path(path).expanduser()
        target.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(target), check_same_thread=False)
        self.db.execute("PRAGMA secure_delete = ON")
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS segments (
                device_id TEXT NOT NULL, segment_id TEXT NOT NULL,
                child_id TEXT NOT NULL, received_at TEXT NOT NULL,
                local_date TEXT NOT NULL, expires_at TEXT NOT NULL,
                transcript TEXT, status TEXT NOT NULL, event_id TEXT,
                PRIMARY KEY(device_id, segment_id)
            );
            CREATE TABLE IF NOT EXISTS events (
                event_id TEXT PRIMARY KEY, data TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS revisions (
                child_id TEXT NOT NULL, local_date TEXT NOT NULL,
                revision INTEGER NOT NULL,
                PRIMARY KEY(child_id, local_date)
            );
            CREATE TABLE IF NOT EXISTS reports (
                child_id TEXT NOT NULL, local_date TEXT NOT NULL,
                revision INTEGER NOT NULL, data TEXT NOT NULL,
                PRIMARY KEY(child_id, local_date)
            );
            CREATE TABLE IF NOT EXISTS local_profile (
                id INTEGER PRIMARY KEY CHECK(id = 1), data TEXT NOT NULL
            );
            DROP TABLE IF EXISTS report_notifications;
        """)
        columns = {row[1] for row in self.db.execute("PRAGMA table_info(segments)")}
        if "transcript_revision" not in columns:
            self.db.execute("ALTER TABLE segments ADD COLUMN transcript_revision INTEGER NOT NULL DEFAULT 0")
            self.db.commit()

    def load_profile(self) -> dict | None:
        row = self.db.execute("SELECT data FROM local_profile WHERE id=1").fetchone()
        return json.loads(row[0]) if row else None

    def save_profile(self, profile: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO local_profile VALUES (1, ?) ON CONFLICT(id) DO UPDATE SET data=excluded.data",
                (json.dumps(profile, ensure_ascii=False),),
            )

    def load(self) -> tuple[dict, dict, dict]:
        segments = {}
        for row in self.db.execute("SELECT device_id, segment_id, child_id, received_at, local_date, expires_at, transcript, status, event_id, transcript_revision FROM segments"):
            device_id, segment_id, child_id, received_at, local_date, expires_at, transcript, status, event_id, transcript_revision = row
            segments[(device_id, segment_id)] = {
                "device_id": device_id, "segment_id": segment_id, "child_id": child_id,
                "received_at": received_at, "local_date": local_date,
                "expires_at": datetime.fromisoformat(expires_at), "transcript": transcript,
                "status": status, "event_id": event_id, "transcript_revision": transcript_revision,
            }
        events = {event_id: json.loads(data) for event_id, data in self.db.execute("SELECT event_id, data FROM events")}
        revisions = {(child_id, day): revision for child_id, day, revision in self.db.execute("SELECT child_id, local_date, revision FROM revisions")}
        return segments, events, revisions

    def save(self, segment: dict, event: dict | None, revision: int) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO segments (device_id, segment_id, child_id, received_at, local_date, expires_at, transcript, status, event_id, transcript_revision) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (segment["device_id"], segment["segment_id"], segment["child_id"],
                 segment["received_at"], segment["local_date"], segment["expires_at"].isoformat(),
                 segment["transcript"], segment["status"], segment["event_id"], segment["transcript_revision"]),
            )
            if event:
                self.db.execute("INSERT INTO events VALUES (?, ?)", (event["event_id"], json.dumps(event, ensure_ascii=False)))
            self.db.execute(
                "INSERT INTO revisions VALUES (?, ?, ?) ON CONFLICT(child_id, local_date) DO UPDATE SET revision=excluded.revision",
                (segment["child_id"], segment["local_date"], revision),
            )

    def save_segment_change(self, segment: dict, changed_events: list[dict], revision: int) -> None:
        with self.db:
            updated = self.db.execute(
                "UPDATE segments SET transcript=?, status=?, event_id=?, transcript_revision=? WHERE device_id=? AND segment_id=?",
                (segment["transcript"], segment["status"], segment["event_id"],
                 segment["transcript_revision"], segment["device_id"], segment["segment_id"]),
            )
            if updated.rowcount != 1:
                raise RuntimeError("segment disappeared during update")
            for event in changed_events:
                self.db.execute(
                    "INSERT INTO events VALUES (?, ?) ON CONFLICT(event_id) DO UPDATE SET data=excluded.data",
                    (event["event_id"], json.dumps(event, ensure_ascii=False)),
                )
            self.db.execute(
                "INSERT INTO revisions VALUES (?, ?, ?) ON CONFLICT(child_id, local_date) DO UPDATE SET revision=excluded.revision",
                (segment["child_id"], segment["local_date"], revision),
            )

    def save_revision(self, event: dict, revision: int, *, erase_transcript: bool) -> None:
        with self.db:
            self.db.execute("UPDATE events SET data=? WHERE event_id=?", (json.dumps(event, ensure_ascii=False), event["event_id"]))
            self.db.execute(
                "INSERT INTO revisions VALUES (?, ?, ?) ON CONFLICT(child_id, local_date) DO UPDATE SET revision=excluded.revision",
                (event["child_id"], event["local_date"], revision),
            )
            if erase_transcript:
                self.db.execute("UPDATE segments SET transcript=NULL WHERE event_id=?", (event["event_id"],))

    def erase_transcript(self, *, device_id: str, segment_id: str) -> None:
        with self.db:
            self.db.execute("UPDATE segments SET transcript=NULL WHERE device_id=? AND segment_id=?", (device_id, segment_id))

    def get_report(self, *, child_id: str, local_date: str, revision: int) -> dict | None:
        row = self.db.execute(
            "SELECT data FROM reports WHERE child_id=? AND local_date=? AND revision=?",
            (child_id, local_date, revision),
        ).fetchone()
        return json.loads(row[0]) if row else None

    def save_report(self, *, child_id: str, local_date: str, revision: int, report: dict) -> None:
        with self.db:
            self.db.execute(
                "INSERT INTO reports VALUES (?, ?, ?, ?) ON CONFLICT(child_id, local_date) DO UPDATE SET revision=excluded.revision, data=excluded.data",
                (child_id, local_date, revision, json.dumps(report, ensure_ascii=False)),
            )
    def close(self) -> None:
        self.db.close()
