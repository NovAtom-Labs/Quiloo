"""Artifact generation entrypoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from junction_lab.config import load_experiment
from junction_lab.physics import summarize
from junction_lab.report import render_report


def run(input_path: Path, output_directory: Path) -> None:
    experiment = load_experiment(input_path)
    summary = summarize(experiment)
    input_sha256 = hashlib.sha256(input_path.read_bytes()).hexdigest()
    output_directory.mkdir(parents=True, exist_ok=True)
    (output_directory / "results.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    (output_directory / "report.md").write_text(
        render_report(summary, input_sha256=input_sha256)
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=Path("experiment.toml"))
    parser.add_argument("--output", type=Path, default=Path("artifacts"))
    arguments = parser.parse_args()
    run(arguments.input, arguments.output)
    return 0
