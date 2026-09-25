#!/usr/bin/env python3
"""Export portable native-build runtime paths for later GitHub Actions steps."""

from __future__ import annotations

import os
import sys
from pathlib import Path


def configure_environment(github_environment: Path) -> None:
    """Append the setup-python interpreter as the DEVSIM execution runtime."""

    with github_environment.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(f"TCAD_DEVSIM_PYTHON={sys.executable}\n")


def main() -> int:
    target = os.getenv("GITHUB_ENV")
    if not target:
        raise RuntimeError("GITHUB_ENV is required")
    configure_environment(Path(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
