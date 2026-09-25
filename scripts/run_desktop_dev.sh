#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"

if [[ ! -x "$REPOSITORY_ROOT/.venv/bin/python" ]]; then
  echo "Agent Kronig development environment is missing. Create .venv and install the project first." >&2
  exit 1
fi

if [[ ! -x "$REPOSITORY_ROOT/desktop/node_modules/.bin/electron" ]]; then
  echo "Desktop dependencies are missing. Run: pnpm --dir desktop install --frozen-lockfile" >&2
  exit 1
fi

if [[ -f "$REPOSITORY_ROOT/.env" ]]; then
  set -a
  # shellcheck disable=SC1091
  source "$REPOSITORY_ROOT/.env"
  set +a
fi

export TCAD_WORKSPACE="${TCAD_WORKSPACE:-$REPOSITORY_ROOT/.tcad-agent-desktop}"
export OPENHANDS_SUPPRESS_BANNER="1"

cd "$REPOSITORY_ROOT"
exec pnpm --dir "$REPOSITORY_ROOT/desktop" start
