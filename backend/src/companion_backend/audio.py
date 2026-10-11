"""Small, conservative WAV checks for the local voice experiment."""

from __future__ import annotations

from array import array
import io
import sys
import wave


def inspect_wav(data: bytes, *, max_seconds: int) -> bool:
    """Return whether PCM has a signal; raise for malformed or too-short audio.

    The amplitude gate catches digital silence only. It is not speech detection:
    background noise can pass, so ASR results still need review.
    """
    try:
        with wave.open(io.BytesIO(data), "rb") as wav:
            frames = wav.getnframes()
            valid = (
                wav.getnchannels() == 1 and wav.getsampwidth() == 2
                and wav.getframerate() == 16000 and wav.getcomptype() == "NONE"
                and 4000 <= frames <= 16000 * max_seconds
            )
            if not valid:
                raise ValueError(f"Expected mono PCM16 16 kHz WAV from 0.25 to {max_seconds} seconds")
            pcm = wav.readframes(frames)
            if len(pcm) != frames * 2:
                raise ValueError("WAV audio is incomplete")
    except (wave.Error, EOFError) as exc:
        raise ValueError("Invalid WAV audio") from exc
    samples = array("h")
    samples.frombytes(pcm)
    if sys.byteorder != "little":
        samples.byteswap()
    return any(abs(sample) > 16 for sample in samples)
