#!/bin/zsh
set -euo pipefail

script_dir="${0:A:h}"
cd "$script_dir"

if [[ -f .env ]]; then
  set -a
  source .env
  set +a
fi

export PYTHONPATH="$script_dir/src${PYTHONPATH:+:$PYTHONPATH}"
exec .venv/bin/python -m tcad_agent.web.launcher
