"""Locate Windows math runtime libraries for the frozen DEVSIM sidecar."""

from __future__ import annotations

import sys
from pathlib import Path


def collect_windows_math_binaries(
    python_prefix: Path = Path(sys.prefix),
    *,
    platform_name: str = sys.platform,
) -> list[tuple[str, str]]:
    if platform_name != "win32":
        return []
    runtime_directory = python_prefix / "Library" / "bin"
    binaries = [
        (str(path.resolve()), "math-runtime")
        for path in sorted(runtime_directory.glob("*.dll"))
        if path.is_file()
    ]
    if not any(Path(source).name.startswith("mkl_rt.") for source, _ in binaries):
        raise RuntimeError(
            "the pinned Windows MKL package did not provide mkl_rt under "
            f"{runtime_directory}"
        )
    return binaries
