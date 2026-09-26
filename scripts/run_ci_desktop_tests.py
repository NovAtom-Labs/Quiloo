#!/usr/bin/env python3
"""Run desktop tests and expose bounded failures as a GitHub annotation."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys

MAX_ANNOTATION_TEXT = 4000


def _command_value(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def failure_annotation(output: str) -> str:
    """Return one bounded, workflow-safe desktop test failure annotation."""

    clean = "".join(
        character
        for character in output
        if character in "\n\r\t" or ord(character) >= 32
    ).strip()
    if not clean:
        clean = "Desktop tests exited without diagnostic output"
    return (
        "::error title=Desktop test suite failed::"
        + _command_value(clean[-MAX_ANNOTATION_TEXT:])
    )


def main() -> int:
    pnpm = shutil.which("pnpm.cmd" if os.name == "nt" else "pnpm")
    if pnpm is None:
        print(failure_annotation("pnpm is not available"), flush=True)
        return 1
    command = [pnpm, "--dir", "desktop", "test"]
    if os.name == "nt":
        command = ["cmd.exe", "/d", "/s", "/c", subprocess.list2cmdline(command)]
    completed = subprocess.run(
        command,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.stdout:
        print(completed.stdout, end="", flush=True)
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr, flush=True)
    if completed.returncode:
        print(
            failure_annotation(f"{completed.stdout}\n{completed.stderr}"),
            flush=True,
        )
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
