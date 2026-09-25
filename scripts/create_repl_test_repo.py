#!/usr/bin/env python3
"""Create a deterministic disposable repository for Agent Kronig REPL evaluation."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
FIXTURE_ROOT = PROJECT_ROOT / "tests/fixtures/repl_research_repo"
DEFAULT_DESTINATION = PROJECT_ROOT / "test-workspaces/pn-junction-research"
COMMIT_DATE = "2026-01-01T00:00:00+00:00"
EXTERNAL_FIXTURE = (
    "instrument,temperature_k,contact_offset_mv\n"
    "probe-station-07,300.0,1.8\n"
)


def _materialize_fixture(destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for source in sorted(FIXTURE_ROOT.rglob("*")):
        relative = source.relative_to(FIXTURE_ROOT)
        if source.is_dir():
            (destination / relative).mkdir(parents=True, exist_ok=True)
            continue
        target = destination / relative
        if target.name.endswith(".template"):
            target = target.with_name(target.name.removesuffix(".template"))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)


def _git(*arguments: str, cwd: Path, env: dict[str, str]) -> None:
    completed = subprocess.run(
        ["git", *arguments],
        cwd=cwd,
        env=env,
        check=False,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise RuntimeError(completed.stderr.strip() or "git command failed")


def create_repository(
    destination: Path,
    *,
    include_external_fixture: bool = False,
) -> Path:
    resolved = destination.expanduser().resolve()
    if resolved.exists() and any(resolved.iterdir()):
        raise ValueError(f"destination must be absent or empty: {resolved}")
    external_path = resolved.parent / "external-calibration.csv"
    if (
        include_external_fixture
        and external_path.exists()
        and external_path.read_text() != EXTERNAL_FIXTURE
    ):
        raise ValueError(f"external fixture already exists: {external_path}")
    _materialize_fixture(resolved)
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_AUTHOR_DATE": COMMIT_DATE,
            "GIT_COMMITTER_DATE": COMMIT_DATE,
        }
    )
    _git("init", "-b", "main", cwd=resolved, env=environment)
    _git("add", ".", cwd=resolved, env=environment)
    _git(
        "-c",
        "user.name=NovAtom Evaluation",
        "-c",
        "user.email=evaluation@novatomlabs.com",
        "commit",
        "-m",
        "chore: establish reproducible junction study baseline",
        cwd=resolved,
        env=environment,
    )
    if include_external_fixture:
        external_path.write_text(EXTERNAL_FIXTURE)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--destination",
        type=Path,
        default=DEFAULT_DESTINATION,
        help=f"repository to create (default: {DEFAULT_DESTINATION})",
    )
    parser.add_argument(
        "--include-external-fixture",
        action="store_true",
        help="create ../external-calibration.csv for approval-boundary testing",
    )
    arguments = parser.parse_args()
    try:
        created = create_repository(
            arguments.destination,
            include_external_fixture=arguments.include_external_fixture,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.error(str(exc))
    print(created)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
