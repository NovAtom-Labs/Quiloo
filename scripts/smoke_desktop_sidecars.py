#!/usr/bin/env python3
"""Execute one canonical simulation through a freshly frozen DEVSIM sidecar."""

from __future__ import annotations

import argparse
import tempfile
from collections.abc import Sequence
from pathlib import Path

import yaml

from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.desktop.devsim_runner import DevsimSidecarRunner
from tcad_agent.domain.models import ExperimentSpec
from tcad_agent.runners.models import RunBudget


def smoke_devsim_sidecar(project_root: Path, target: Path) -> None:
    """Compile and execute the reviewed reference through the frozen executable."""

    suffix = ".exe" if target.name.startswith("win-") else ""
    executable = target / "devsim" / f"agent-kronig-devsim{suffix}"
    if not executable.is_file():
        raise FileNotFoundError(f"frozen DEVSIM sidecar is missing: {executable}")

    payload = yaml.safe_load((project_root / "examples" / "pn-junction.yaml").read_text())
    spec = ExperimentSpec.model_validate(payload)
    adapter = DevsimAdapter.from_defaults()
    with tempfile.TemporaryDirectory(prefix="agent-kronig-sidecar-smoke-") as directory:
        job = adapter.compile(spec, Path(directory) / "compiled")
        native = DevsimSidecarRunner(executable).run(job, RunBudget(seconds=120))
        if native.status != "completed":
            diagnostic = native.stderr_path.read_text(errors="replace")[-2000:]
            raise RuntimeError(
                f"frozen DEVSIM sidecar failed with status {native.status}: {diagnostic}"
            )
        result = adapter.normalize(native)
        if not result.bias_points or not all(point.converged for point in result.bias_points):
            raise RuntimeError("frozen DEVSIM sidecar returned unconverged canonical results")

    print(
        "Frozen DEVSIM sidecar completed "
        f"{len(result.bias_points)} converged canonical bias points."
    )


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("target", type=Path)
    arguments = parser.parse_args(argv)
    smoke_devsim_sidecar(Path.cwd(), arguments.target.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
