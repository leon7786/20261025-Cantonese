#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"

if [ ! -d .venv ]; then
  echo "==> 建立虛擬環境 .venv"
  python3 -m venv .venv
fi

echo "==> 安裝依賴"
./.venv/bin/pip install -q --upgrade pip
./.venv/bin/pip install -q -r requirements.txt

if ! command -v espeak-ng >/dev/null 2>&1; then
  echo "提示：未安裝 espeak-ng，離線引擎將不可用（apt install espeak-ng / brew install espeak-ng）"
fi

echo "==> http://${HOST:-127.0.0.1}:${PORT:-8000}"
exec ./.venv/bin/python -m app
