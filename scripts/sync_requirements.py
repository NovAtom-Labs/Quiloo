#!/usr/bin/env python3
"""Synchronize install and lock requirements from pyproject.toml."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from tcad_agent.dependency_sync import main

if __name__ == "__main__":
    raise SystemExit(main())
