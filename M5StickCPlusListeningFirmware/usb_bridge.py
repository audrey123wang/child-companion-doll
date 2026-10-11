#!/usr/bin/env python3
"""Receive live ADPCM from M5StickC Plus USB and POST a WAV to the local gateway.

Audio exists in process memory only. No recording or transcript is written to disk.
"""

import argparse
import io
import json
import re
import struct
import sys
import time
import uuid
import urllib.error
import urllib.parse
import urllib.request
import wave
import zlib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work" / "pydeps"))
import serial  # noqa: E402

TOKEN_FILE = ROOT / "work" / "voice-gateway-token.txt"
SAMPLE_RATE = 16000
ADPCM_BYTES = 48000
ADPCM_STEPS = (
    7,8,9,10,11,12,13,14,16,17,19,21,23,25,28,31,34,37,41,45,50,55,60,66,73,
    80,88,97,107,118,130,143,157,173,190,209,230,253,279,307,337,371,408,
    449,494,544,598,658,724,796,876,963,1060,1166,1282,1411,1552,1707,
    1878,2066,2272,2499,2749,3024,3327,3660,4026,4428,4871,5358,5894,
    6484,7132,7845,8630,9493,10442,11487,12635,13899,15289,16818,18500,
    20350,22385,24623,27086,29794,32767
)
ADPCM_INDEX = (-1,-1,-1,-1,2,4,6,8,-1,-1,-1,-1,2,4,6,8)


def decode_adpcm(data):
    predictor = 0
    index = 0
    samples = []
    for byte in data:
        for code in (byte >> 4, byte & 15):
            step = ADPCM_STEPS[index]
            adjustment = step >> 3
            if code & 4:
                adjustment += step
            if code & 2:
                adjustment += step >> 1
            if code & 1:
                adjustment += step >> 2
            predictor += -adjustment if code & 8 else adjustment
            predictor = max(-32768, min(32767, predictor))
            index = max(0, min(88, index + ADPCM_INDEX[code]))
            samples.append(predictor)
    return samples


def read_exact(port, length, timeout=25):
    data = bytearray()
    deadline = time.monotonic() + timeout
    while len(data) < length and time.monotonic() < deadline:
        data.extend(port.read(min(4096, length - len(data))))
    if len(data) != length:
        raise RuntimeError(f"USB audio incomplete: {len(data)}/{length} bytes")
    return bytes(data)


def make_wav(samples):
    output = io.BytesIO()
    with wave.open(output, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(2)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return output.getvalue()


def send_to_gateway(wav_data, device_id, token, gateway):
    request = urllib.request.Request(
        gateway.rstrip("/") + "/v1/utterances",
        data=wav_data,
        headers={
            "Authorization": "Bearer " + token,
            "X-Device-ID": device_id,
            "Content-Type": "audio/wav",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.load(response)
        if response.status != 202:
            raise RuntimeError(f"Gateway returned HTTP {response.status}")
    return body["id"]


def send_to_scene(wav_data, device_id, token, gateway):
    """Send to the new synchronous ASR endpoint; do not report delivery early."""
    segment_id = uuid.uuid4().hex
    request = urllib.request.Request(
        gateway.rstrip("/") + "/v1/device/segments",
        data=wav_data,
        headers={
            "Authorization": "Bearer " + token,
            "X-Device-ID": device_id,
            "X-Segment-ID": segment_id,
            "Content-Type": "audio/wav",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            body = json.load(response)
            if response.status != 200 or body.get("segment_id") != segment_id:
                raise RuntimeError("Scene backend did not confirm the segment")
    except urllib.error.HTTPError as error:
        if error.code == 502:
            try:
                detail = json.load(error).get("detail", "")
            except (ValueError, AttributeError):
                detail = ""
            if isinstance(detail, str) and detail.startswith(("ASR ", "transcription ", "invalid ASR ", "16 kHz ")):
                raise RuntimeError(f"Scene backend HTTP 502: {detail}") from None
        raise
    if body.get("status") not in {"understood", "unclassified", "unreadable"}:
        raise RuntimeError("Scene backend did not finish transcription")
    return body["status"]


def wait_job(job_id, device_id, token, gateway):
    path = "/v1/jobs?device=" + urllib.parse.quote(device_id)
    for _ in range(12):
        request = urllib.request.Request(
            gateway.rstrip("/") + path,
            headers={"Authorization": "Bearer " + token},
        )
        with urllib.request.urlopen(request, timeout=5) as response:
            jobs = json.load(response)["jobs"]
        job = next((item for item in jobs if item["id"] == job_id), None)
        if job and job["status"] != "processing":
            return job["status"]
        time.sleep(0.5)
    return "processing"


def wait_ready(port):
    deadline = time.monotonic() + 30
    next_request = 0
    while time.monotonic() < deadline:
        if time.monotonic() >= next_request:
            port.write(b"@transport=usb\n")
            next_request = time.monotonic() + 2
        line = port.readline().decode("utf-8", "replace").strip()
        if line == "CONFIG transport=usb":
            return
    raise RuntimeError("Device did not enter USB bridge mode")


def receive_one(port, token, gateway, api_mode="legacy"):
    while True:
        line = port.readline().decode("utf-8", "replace").strip()
        if not line:
            continue
        if line.startswith("USB_AUDIO_BEGIN "):
            break
        if line.startswith("VOICE ") or line.startswith("PAGE "):
            print(line, flush=True)
    fields = line.split()
    if len(fields) != 5 or fields[1:4] != ["1", str(ADPCM_BYTES), str(SAMPLE_RATE)]:
        raise RuntimeError("Unexpected USB audio header")
    device_id = fields[4]
    if not re.fullmatch(r"stickc-[0-9a-f]{12}", device_id):
        raise RuntimeError("Invalid device ID")
    if api_mode == "scene":
        print(f"Device ID for parent binding: {device_id}", flush=True)
    print("Receiving six-second microphone stream...", flush=True)
    payload = read_exact(port, ADPCM_BYTES)
    trailer = ""
    for _ in range(4):
        trailer = port.readline().decode("ascii", "replace").strip()
        if trailer.startswith("USB_AUDIO_END "):
            break
    parts = trailer.split()
    if len(parts) != 4:
        raise RuntimeError("Missing USB audio trailer")
    expected_checksum = int(parts[1], 16)
    captured = int(parts[2])
    microphone_ok = parts[3] == "1"
    if zlib.adler32(payload) != expected_checksum:
        raise RuntimeError("USB audio checksum mismatch")
    if not microphone_ok or not 0 < captured <= ADPCM_BYTES * 2:
        raise RuntimeError("Microphone capture failed")
    decoded = decode_adpcm(payload)[:captured]
    peak = max(abs(sample) for sample in decoded)
    wav_data = make_wav(decoded)
    print(f"Received {captured / SAMPLE_RATE:.2f}s, peak={peak}, WAV={len(wav_data)} bytes", flush=True)
    if api_mode == "scene":
        status = send_to_scene(wav_data, device_id, token, gateway)
        port.write(b"@bridge=failed\n" if status == "unreadable" else b"@bridge=delivered\n")
        print(f"Scene backend completed ASR: {status}", flush=True)
    else:
        job_id = send_to_gateway(wav_data, device_id, token, gateway)
        port.write(b"@bridge=delivered\n")
        print(f"Gateway accepted audio: HTTP 202, job={job_id}", flush=True)
        try:
            print(f"Gateway processing status: {wait_job(job_id, device_id, token, gateway)}", flush=True)
        except urllib.error.URLError as error:
            print(f"Gateway job status unavailable: {error}", flush=True)


def main():
    parser = argparse.ArgumentParser(description="M5StickC Plus USB audio bridge")
    parser.add_argument("--port", default="/dev/cu.usbserial-59526C1D38")
    parser.add_argument("--gateway", default="http://127.0.0.1:8765")
    parser.add_argument("--api-mode", choices=("legacy", "scene"), default="legacy")
    parser.add_argument("--test-once", action="store_true", help="start one recording using the serial A-key mirror")
    args = parser.parse_args()
    token = TOKEN_FILE.read_text().strip()
    if not token:
        raise SystemExit("Missing gateway token; run configure_usb.py first")
    with serial.Serial(args.port, 115200, timeout=0.5, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        wait_ready(port)
        print("USB bridge ready. On Listening, press the device's A button to record.", flush=True)
        if args.test_once:
            port.write(b"a")
        try:
            while True:
                try:
                    receive_one(port, token, args.gateway, args.api_mode)
                    if args.test_once:
                        break
                except (RuntimeError, urllib.error.URLError, ValueError) as error:
                    print(f"Bridge error: {error}", flush=True)
                    port.write(b"@bridge=failed\n")
                    if args.test_once:
                        raise
        finally:
            port.write(b"@transport=wifi\n")


if __name__ == "__main__":
    main()
