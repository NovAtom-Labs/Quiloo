#!/usr/bin/env python3
"""Validate the shared Agent Kronig release identity."""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ALPHA_VERSION = re.compile(
    r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)-alpha\.([1-9][0-9]*)$"
)


@dataclass(frozen=True)
class ReleaseIdentity:
    """One validated version and its canonical Git tag."""

    version: str
    tag: str


def _python_version(root: Path) -> str:
    with (root / "pyproject.toml").open("rb") as handle:
        payload: dict[str, Any] = tomllib.load(handle)
    try:
        return str(payload["project"]["version"])
    except (KeyError, TypeError) as exc:
        raise ValueError("pyproject.toml does not define project.version") from exc


def _desktop_version(root: Path) -> str:
    try:
        payload = json.loads((root / "desktop" / "package.json").read_text())
        return str(payload["version"])
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError("desktop/package.json does not define a valid version") from exc


def load_release_identity(root: Path, tag: str | None = None) -> ReleaseIdentity:
    """Load matching alpha versions and validate their canonical tag."""

    root = root.resolve()
    python_version = _python_version(root)
    desktop_version = _desktop_version(root)
    if python_version != desktop_version:
        raise ValueError(
            "Python and desktop versions differ: "
            f"{python_version!r} != {desktop_version!r}"
        )
    if ALPHA_VERSION.fullmatch(python_version) is None:
        raise ValueError(
            "Release version must use MAJOR.MINOR.PATCH-alpha.N format"
        )
    expected_tag = f"v{python_version}"
    selected_tag = tag or expected_tag
    if selected_tag != expected_tag:
        raise ValueError(
            f"Release tag {selected_tag!r} does not match {expected_tag!r}"
        )
    return ReleaseIdentity(version=python_version, tag=selected_tag)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--tag")
    arguments = parser.parse_args()
    try:
        identity = load_release_identity(arguments.root, arguments.tag)
    except (OSError, ValueError) as exc:
        print(f"Release identity is invalid: {exc}", file=sys.stderr)
        return 2
    print(f"version={identity.version}")
    print(f"tag={identity.tag}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
