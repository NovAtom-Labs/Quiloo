#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
cd "$script_dir"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

exec .venv/bin/tcad-agent-web
