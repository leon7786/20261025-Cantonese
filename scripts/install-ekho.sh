#!/usr/bin/env bash
# Build and install Ekho (Cantonese TTS) from source.
# Ubuntu/Debian only; needs sudo for apt and /usr/local install.
set -euo pipefail

sudo apt-get update
sudo apt-get install -y \
  build-essential autoconf automake libtool gettext pkg-config \
  libsndfile1-dev libespeak-ng-dev libmp3lame-dev libutfcpp-dev \
  libpulse-dev libcurl4-openssl-dev

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git clone --depth 1 https://github.com/hgneng/ekho.git "$tmp/ekho"
cd "$tmp/ekho"

./autogen.sh
./configure --prefix=/usr/local
make -j"$(nproc)"
# install-data-hook may fail on optional assets; binary + voice data still install.
make install || true

if ! command -v ekho >/dev/null 2>&1; then
  echo "ekho 安裝失敗" >&2
  exit 1
fi

ekho -v Cantonese -o /tmp/ekho-check.wav "你好" && echo "OK: ekho 粵語可用"
