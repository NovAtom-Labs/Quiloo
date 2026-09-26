#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIRECTORY="$(cd -- "$(dirname -- "$0")" && pwd)"

exec "$SCRIPT_DIRECTORY/scripts/run_desktop_dev.sh"
