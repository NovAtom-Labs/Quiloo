#!/usr/bin/env python3
"""Build target-native desktop installers."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from collections.abc import Mapping, Sequence


def sanitized_builder_environment(environment: Mapping[str, str]) -> dict[str, str]:
    """Drop empty signing inputs that electron-builder treats as filesystem paths."""

    result = dict(environment)
    for name in ("CSC_LINK", "CSC_KEY_PASSWORD"):
        if not result.get(name):
            result.pop(name, None)
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("platform", choices=("linux", "mac", "win"))
    parser.add_argument("arch", choices=("arm64", "x64"))
    arguments = parser.parse_args(argv)

    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if pnpm is None:
        raise RuntimeError("pnpm is required to build native installers")
    command = [
        pnpm,
        "--dir",
        "desktop",
        "exec",
        "electron-builder",
        "--config",
        "electron-builder.yml",
        f"--{arguments.platform}",
        f"--{arguments.arch}",
    ]
    if os.name == "nt":
        command = ["cmd.exe", "/d", "/s", "/c", subprocess.list2cmdline(command)]
    return subprocess.run(
        command,
        check=False,
        env=sanitized_builder_environment(os.environ),
    ).returncode


if __name__ == "__main__":
    raise SystemExit(main())
