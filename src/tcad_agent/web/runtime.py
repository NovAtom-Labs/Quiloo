"""Non-secret identity for the local web runtime and its model configuration."""

from __future__ import annotations

import hashlib
import os
from pathlib import Path

_HASHED_SUFFIXES = {".css", ".html", ".j2", ".js", ".py", ".yaml", ".yml"}


def runtime_fingerprint() -> str:
    digest = hashlib.sha256()
    for name, default in (
        ("LLM_MODEL", ""),
        ("AWS_REGION_NAME", "ap-south-1"),
        ("TCAD_REASONING_EFFORT", "medium"),
    ):
        digest.update(name.encode())
        digest.update(b"\0")
        digest.update(os.getenv(name, default).encode())
        digest.update(b"\0")

    package_root = Path(__file__).resolve().parents[1]
    for path in sorted(
        item
        for item in package_root.rglob("*")
        if item.is_file()
        and item.suffix in _HASHED_SUFFIXES
        and "__pycache__" not in item.parts
    ):
        digest.update(path.relative_to(package_root).as_posix().encode())
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()[:16]
