"""One-shot local Volc TTS 2.0 check; never persists the key or generated audio."""

from __future__ import annotations

import argparse
from getpass import getpass
from pathlib import Path
import subprocess
import tempfile

from companion_backend.providers import TtsError
from companion_backend.volc_speech import DEFAULT_SPEAKER, VolcTts2


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify Volc TTS 2.0 with a short Mandarin sample")
    parser.add_argument("--speaker", default=DEFAULT_SPEAKER, help="A 2.0 voice enabled for your account")
    args = parser.parse_args()
    key = getpass("火山引擎 API Key（输入不显示）: ")
    try:
        audio = VolcTts2(key, speaker=args.speaker).synthesize("你好，我是小猫米米。很高兴和你聊天。")
    except (TtsError, ValueError) as exc:
        print(f"TTS 生成失败：{exc}")
        return 1
    print(f"TTS 生成成功：收到 {len(audio)} 字节 MP3，开始播放。")
    with tempfile.TemporaryDirectory(prefix="companion-tts-") as directory:
        path = Path(directory) / "sample.mp3"
        path.write_bytes(audio)
        try:
            subprocess.run(["afplay", str(path)], check=True)
        except (OSError, subprocess.CalledProcessError):
            print("MP3 已生成，但 Mac 播放失败；请检查系统输出设备。")
            return 2
    print("播放结束，临时 MP3 已删除。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
