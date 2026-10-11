#!/bin/sh
set -eu
cd "$(dirname "$0")/../.."
token_file="$(pwd)/work/voice-gateway-token.txt"
if [ ! -f "$token_file" ]; then
  echo "请先运行 configure_usb.py，以生成与设备相同的网关令牌。" >&2
  exit 1
fi
VOICE_GATEWAY_TOKEN="$(cat "$token_file")"
export VOICE_GATEWAY_TOKEN
if [ -z "${OPENAI_API_KEY:-}" ]; then
  VOICE_MODE=mock
  export VOICE_MODE
  echo "接收程序以模拟模式启动：只验证录音上传，不调用云端。"
fi
exec python3 outputs/M5StickCPlusVoice/gateway/gateway.py
