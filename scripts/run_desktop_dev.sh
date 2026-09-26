#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
REPOSITORY_ROOT="$(cd -- "$SCRIPT_DIRECTORY/.." && pwd)"

if [[ ! -x "$REPOSITORY_ROOT/.venv/bin/python" ]]; then
  echo "Agent Kronig development setup is missing. Run: python3.13 scripts/bootstrap_dev.py" >&2
  exit 1
fi

exec "$REPOSITORY_ROOT/.venv/bin/python" "$REPOSITORY_ROOT/scripts/run_desktop_dev.py"
