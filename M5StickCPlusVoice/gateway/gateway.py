#!/usr/bin/env python3
"""Small LAN gateway for M5StickC Plus push-to-talk audio.

The ESP32 sends a 16 kHz mono WAV. A phone or Mac polls for completed jobs and
plays the generated MP3. OPENAI_API_KEY remains on this gateway only.
"""

import base64
import io
import json
import math
import os
import struct
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import wave
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


HOST = os.getenv("VOICE_HOST", "0.0.0.0")
PORT = int(os.getenv("VOICE_PORT", "8765"))
TOKEN = os.getenv("VOICE_GATEWAY_TOKEN", "")
API_KEY = os.getenv("OPENAI_API_KEY", "")
MODE = os.getenv("VOICE_MODE", "openai")
ASR_MODEL = os.getenv("VOICE_ASR_MODEL", "gpt-transcribe")
TEXT_MODEL = os.getenv("VOICE_TEXT_MODEL", "gpt-4o-mini")
TTS_MODEL = os.getenv("VOICE_TTS_MODEL", "gpt-4o-mini-tts")
TTS_VOICE = os.getenv("VOICE_TTS_VOICE", "coral")
MAX_WAV = 220_000
jobs = {}
lock = threading.Lock()


def openai_request(path, data, content_type, *, binary=False):
    request = urllib.request.Request(
        "https://api.openai.com/v1/" + path,
        data=data,
        headers={"Authorization": "Bearer " + API_KEY, "Content-Type": content_type},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            body = response.read()
    except urllib.error.HTTPError as exc:
        detail = exc.read(1000).decode("utf-8", "replace")
        raise RuntimeError("OpenAI HTTP %s: %s" % (exc.code, detail)) from exc
    return body if binary else json.loads(body)


def transcribe(wav_bytes):
    boundary = "----voice" + uuid.uuid4().hex
    parts = []
    for name, value in (("model", ASR_MODEL),):
        parts.append(("--%s\r\nContent-Disposition: form-data; name=\"%s\"\r\n\r\n%s\r\n" % (boundary, name, value)).encode())
    parts.append(("--%s\r\nContent-Disposition: form-data; name=\"file\"; filename=\"voice.wav\"\r\nContent-Type: audio/wav\r\n\r\n" % boundary).encode())
    parts.append(wav_bytes)
    parts.append(("\r\n--%s--\r\n" % boundary).encode())
    result = openai_request("audio/transcriptions", b"".join(parts), "multipart/form-data; boundary=" + boundary)
    return result["text"].strip()


def answer(text):
    data = json.dumps({
        "model": TEXT_MODEL,
        "instructions": "你是一个简洁的中文语音助手。用自然、简短的口语回答；不要使用 Markdown。",
        "input": text,
        "max_output_tokens": 220,
    }, ensure_ascii=False).encode()
    result = openai_request("responses", data, "application/json")
    chunks = [part.get("text", "") for item in result.get("output", [])
              for part in item.get("content", []) if part.get("type") == "output_text"]
    response = "".join(chunks).strip()
    if not response:
        raise RuntimeError("The text model returned no speech text")
    return response


def speak(text):
    data = json.dumps({"model": TTS_MODEL, "voice": TTS_VOICE, "input": text,
                       "response_format": "mp3"}, ensure_ascii=False).encode()
    return openai_request("audio/speech", data, "application/json", binary=True)


def mock_tone():
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(16000)
        samples = [int(5000 * math.sin(2 * math.pi * 660 * i / 16000)) for i in range(4800)]
        wav.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return output.getvalue()


def process(job_id, audio):
    try:
        if MODE == "mock":
            transcript, response, output, mime = ("测试录音", "链路测试成功", mock_tone(), "audio/wav")
        else:
            transcript = transcribe(audio)
            response = answer(transcript)
            output, mime = speak(response), "audio/mpeg"
        with lock:
            jobs[job_id].update(status="done", transcript=transcript, answer=response,
                                audio=output, mime=mime)
    except Exception as exc:
        with lock:
            jobs[job_id].update(status="error", error=str(exc)[:500])


class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def send_bytes(self, status, data, mime="application/json"):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def send_json(self, status, value):
        self.send_bytes(status, json.dumps(value, ensure_ascii=False).encode())

    def authorized(self):
        if not TOKEN or self.headers.get("Authorization") != "Bearer " + TOKEN:
            self.send_json(401, {"error": "Missing or invalid gateway token"})
            return False
        return True

    def do_POST(self):
        if self.path != "/v1/utterances":
            return self.send_json(404, {"error": "Not found"})
        if not self.authorized():
            return
        device = self.headers.get("X-Device-ID", "")
        if not device or len(device) > 64:
            return self.send_json(400, {"error": "Invalid device ID"})
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if not 44 <= length <= MAX_WAV:
            return self.send_json(413, {"error": "WAV size outside limits"})
        audio = self.rfile.read(length)
        try:
            with wave.open(io.BytesIO(audio), "rb") as wav:
                valid = wav.getnchannels() == 1 and wav.getsampwidth() == 2 and wav.getframerate() == 16000
        except (wave.Error, EOFError):
            valid = False
        if not valid:
            return self.send_json(400, {"error": "Expected mono 16-bit 16 kHz WAV"})
        job_id = uuid.uuid4().hex
        with lock:
            jobs[job_id] = {"id": job_id, "device": device, "created": time.time(), "status": "processing"}
        threading.Thread(target=process, args=(job_id, audio), daemon=True).start()
        self.send_json(202, {"id": job_id, "status": "processing"})

    def do_GET(self):
        if self.path == "/health":
            return self.send_json(200, {"status": "ok", "mode": MODE})
        if not self.authorized():
            return
        parsed = urllib.parse.urlsplit(self.path)
        if parsed.path == "/v1/jobs":
            device = urllib.parse.parse_qs(parsed.query).get("device", [""])[0]
            if not device:
                return self.send_json(400, {"error": "Missing device"})
            with lock:
                items = [{k: v for k, v in j.items() if k not in ("audio", "mime")}
                         for j in jobs.values() if j["device"] == device]
            return self.send_json(200, {"jobs": sorted(items, key=lambda j: j["created"], reverse=True)[:10]})
        if parsed.path.startswith("/v1/audio/"):
            job_id = parsed.path.rsplit("/", 1)[-1]
            with lock:
                job = jobs.get(job_id)
            if not job or job["status"] != "done":
                return self.send_json(404, {"error": "Audio unavailable"})
            return self.send_bytes(200, job["audio"], job["mime"])
        self.send_json(404, {"error": "Not found"})


def main():
    if not TOKEN:
        raise SystemExit("Set VOICE_GATEWAY_TOKEN to a random secret")
    if MODE != "mock" and not API_KEY:
        raise SystemExit("Set OPENAI_API_KEY, or set VOICE_MODE=mock for a local test")
    print("Voice gateway listening on %s:%s (%s)" % (HOST, PORT, MODE), flush=True)
    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()


if __name__ == "__main__":
    main()
