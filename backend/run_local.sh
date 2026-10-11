#!/bin/zsh
set -eu

backend_dir=${0:A:h}
project_dir=${backend_dir:h}
env_file="$backend_dir/.env"

if [[ ! -f "$env_file" ]]; then
  print -u2 '缺少 backend/.env；请先配置本机模型密钥。'
  exit 1
fi

set -a
source "$env_file"
set +a

export APP_ENV=local
export LOCAL_SQLITE_PATH="${LOCAL_SQLITE_PATH:-$project_dir/work/scene.sqlite3}"
export LOCAL_DEVICE_TOKEN_FILE="${LOCAL_DEVICE_TOKEN_FILE:-$project_dir/work/voice-gateway-token.txt}"

cd "$backend_dir"
exec .venv/bin/python -m uvicorn companion_backend.main:app --host 127.0.0.1 --port "${PORT:-8766}"
