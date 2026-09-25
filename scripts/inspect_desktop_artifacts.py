#!/usr/bin/env python3
"""Inventory desktop artifacts and fail closed on common credential material."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path

SECRET_PATTERNS = (
    re.compile(rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    re.compile(rb"(?<![0-9A-Z])AKIA[0-9A-Z]{16}(?![0-9A-Z])"),
    re.compile(rb"ABSKQmVkcm9ja0FQSUtleS"),
    re.compile(rb"AWS_SECRET_ACCESS_KEY\s*[:=]"),
)


def inspect_artifacts(root: Path) -> tuple[tuple[str, int, str], ...]:
    root = root.resolve()
    files = tuple(sorted(path for path in root.rglob("*") if path.is_file()))
    if not files:
        raise FileNotFoundError(f"no desktop artifacts found under {root}")
    inventory: list[tuple[str, int, str]] = []
    for path in files:
        relative = path.relative_to(root).as_posix()
        if path.name == ".env" or path.name.startswith(".env."):
            raise ValueError(f"environment file found in artifact output: {relative}")
        digest = hashlib.sha256()
        overlap = b""
        scan_content = "/_internal/" not in f"/{relative}" and "/Frameworks/" not in f"/{relative}"
        with path.open("rb") as handle:
            while chunk := handle.read(1024 * 1024):
                digest.update(chunk)
                inspected = overlap + chunk
                if scan_content and any(
                    pattern.search(inspected) for pattern in SECRET_PATTERNS
                ):
                    raise ValueError(f"credential pattern found in artifact: {relative}")
                overlap = inspected[-256:]
        inventory.append((relative, path.stat().st_size, digest.hexdigest()))
    return tuple(inventory)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    arguments = parser.parse_args()
    inventory = inspect_artifacts(arguments.root)
    for relative, size, digest in inventory:
        path = Path(relative)
        if len(path.parts) == 1:
            print(f"{digest}  {size:>12}  {relative}")
    print(f"Verified {len(inventory)} files without application credential material.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
