#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")" && pwd)"
export PATH="$ROOT/.tools/node/bin:$PATH"

cd "$ROOT"
if [[ -f .venv/bin/activate ]]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# Ensure React build exists for single-port serve
if [[ ! -f web/dist/index.html ]]; then
  echo "Building React UI…"
  (cd web && npm install && npm run build)
fi

exec python -u server.py
