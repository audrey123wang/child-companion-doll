#!/bin/sh
set -eu
cd "$(dirname "$0")"
if [ -z "${VOICE_GATEWAY_TOKEN:-}" ]; then
  VOICE_GATEWAY_TOKEN="$(openssl rand -hex 16)"
  export VOICE_GATEWAY_TOKEN
fi
echo "Gateway token (enter in companion app): $VOICE_GATEWAY_TOKEN"
if [ -z "${OPENAI_API_KEY:-}" ]; then
  VOICE_MODE=mock
  export VOICE_MODE
  echo "OPENAI_API_KEY is unset; running a local audio-path test with a tone."
fi
exec python3 gateway.py
