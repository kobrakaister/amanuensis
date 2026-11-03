#!/bin/sh
set -eu
studio="${HOME}/mba-studio"
bindir="${studio}/bin"
mkdir -p "$bindir"
export UV_PROJECT_ENVIRONMENT="${studio}/.venv"
export UV_PYTHON_INSTALL_DIR="${studio}/python"
export UV_CACHE_DIR="${studio}/cache"
uvbin="${bindir}/uv"
if [ ! -x "$uvbin" ]; then
  arch=$(uname -m)
  case "$arch" in
    arm64)
      url="https://github.com/astral-sh/uv/releases/download/0.11.16/uv-aarch64-apple-darwin.tar.gz"
      sum="2b25be1af546be330b340b0a76b99f989daa6d92678fdffb87438e661e9d88fb"
      member="uv-aarch64-apple-darwin/uv"
      ;;
    x86_64)
      url="https://github.com/astral-sh/uv/releases/download/0.11.16/uv-x86_64-apple-darwin.tar.gz"
      sum="6b91ae3de155f51bd1f5b74814821c79f016a176561f252cd9ddfb976939af2e"
      member="uv-x86_64-apple-darwin/uv"
      ;;
    *)
      echo "architettura non prevista: $arch" >&2
      exit 1
      ;;
  esac
  archive="${bindir}/uv.tar.gz"
  curl -fsSL "$url" -o "$archive"
  actual=$(shasum -a 256 "$archive" | awk '{print $1}')
  if [ "$actual" != "$sum" ]; then
    rm -f "$archive"
    echo "uv: checksum" >&2
    exit 1
  fi
  tar -xzf "$archive" -C "$bindir" "$member"
  mv "${bindir}/${member}" "$uvbin"
  chmod +x "$uvbin"
fi
root=$(CDPATH= cd -- "$(dirname "$0")/.." && pwd)
exec "$uvbin" run --project "$root" lecture-study up
