"""Command-line wrapper for target-native desktop sidecar builds."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tcad_agent.desktop.build_sidecars import main

if __name__ == "__main__":
    raise SystemExit(main())
