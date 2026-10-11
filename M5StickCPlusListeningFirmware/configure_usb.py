#!/usr/bin/env python3
"""Provision the connected M5StickC Plus over USB without echoing secrets."""

import getpass
import os
import re
import secrets
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "work" / "pydeps"))
import serial  # noqa: E402

TOKEN_FILE = ROOT / "work" / "voice-gateway-token.txt"


def mac_wifi_ip():
    result = subprocess.run(["ifconfig", "en0"], capture_output=True, text=True, check=False)
    match = re.search(r"\binet (\d+\.\d+\.\d+\.\d+)\b", result.stdout)
    return match.group(1) if match else ""


def read_token():
    if TOKEN_FILE.exists():
        return TOKEN_FILE.read_text().strip()
    token = secrets.token_hex(16)
    fd = os.open(TOKEN_FILE, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w") as output:
        output.write(token + "\n")
    return token


def wait_for(port, marker, timeout=8):
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        text += port.read(4096).decode("utf-8", "replace")
        if marker in text:
            return text
    raise RuntimeError(f"设备没有回复 {marker}；请检查串口及固件版本")


def wait_wifi_result(port, timeout=23):
    deadline = time.monotonic() + timeout
    text = ""
    while time.monotonic() < deadline:
        text += port.read(4096).decode("utf-8", "replace")
        for line in text.splitlines():
            if "VOICE Wi-Fi connected" in line or "VOICE Wi-Fi failed" in line:
                return line.strip()
    raise RuntimeError("设备 Wi-Fi 连接超时")


def send(port, key, value):
    if "\n" in value or "\r" in value:
        raise ValueError(f"{key} 不能包含换行")
    port.reset_input_buffer()
    port.write((f"@{key}={value}\n").encode())
    wait_for(port, f"CONFIG saved {key}")
    print(f"已写入 {key}")


def main():
    serial_port = sys.argv[1] if len(sys.argv) > 1 else "/dev/cu.usbserial-59526C1D38"
    suggested = mac_wifi_ip()
    default_url = f"http://{suggested}:8765" if suggested else ""
    ssid = input("2.4 GHz Wi-Fi 名称（SSID）：").strip()
    password = getpass.getpass("Wi-Fi 密码（输入不显示）：")
    gateway_url = input(f"网关地址 [{default_url}]：").strip() or default_url
    if not ssid or not gateway_url:
        raise SystemExit("SSID 和网关地址不能为空")
    token = read_token()
    with serial.Serial(serial_port, 115200, timeout=0.3) as port:
        time.sleep(3)
        send(port, "ssid", ssid)
        send(port, "pass", password)
        send(port, "url", gateway_url)
        send(port, "token", token)
        port.reset_input_buffer()
        port.write(b"@connect\n")
        line = wait_wifi_result(port)
        print(line)
        if "Wi-Fi connected" not in line:
            raise SystemExit("Wi-Fi 未连通。请检查 SSID、密码和 2.4 GHz 网络设置。")
    print("设备已连 Wi-Fi。另开终端运行 ./run_local_gateway.sh，再在 Listening 表情下按 A 测试上传。")


if __name__ == "__main__":
    main()
