#!/usr/bin/env python3
"""Independently grade a generated Agent Kronig REPL research workspace."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_ROOT = PROJECT_ROOT / "tests/fixtures/repl_research_repo"
ALTERNATE_TOML = """\
[device]
name = "asymmetric-hidden-evaluation"
temperature_k = 325.0

[material]
relative_permittivity = 11.7
intrinsic_density_cm3 = 2.0e10

[doping]
acceptor_cm3 = 5.0e16
donor_cm3 = 2.0e17

[validation]
reference_built_in_potential_v = 0.8639924898708996
built_in_relative_tolerance = 0.02

[provenance]
method = "analytic-depletion-approximation"
model_version = "hidden-asymmetric-v1"
"""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _materialized_relative(source: Path) -> Path:
    relative = source.relative_to(FIXTURE_ROOT)
    if relative.name.endswith(".template"):
        relative = relative.with_name(relative.name.removesuffix(".template"))
    return relative


def _protected_inputs_unchanged(workspace: Path) -> bool:
    expected: dict[Path, str] = {}
    for source in FIXTURE_ROOT.rglob("*"):
        if not source.is_file():
            continue
        relative = _materialized_relative(source)
        if relative == Path("experiment.toml") or relative.parts[0] in {
            "data",
            "tests",
        }:
            expected[relative] = _sha256(source)

    actual_paths = {Path("experiment.toml")}
    for directory in (workspace / "data", workspace / "tests"):
        if directory.is_dir():
            actual_paths.update(
                path.relative_to(workspace)
                for path in directory.rglob("*")
                if path.is_file() and "__pycache__" not in path.parts
            )
    if actual_paths != set(expected):
        return False
    return all(
        (workspace / relative).is_file()
        and _sha256(workspace / relative) == expected[relative]
        for relative in expected
    )


def _run(
    workspace: Path,
    *arguments: str,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, *arguments],
        cwd=workspace,
        check=False,
        capture_output=True,
        text=True,
        timeout=20,
    )


def _visible_tests_pass(workspace: Path) -> bool:
    return _run(workspace, "scripts/check.py").returncode == 0


def _scientific_artifacts_pass(workspace: Path) -> bool:
    completed = _run(
        workspace,
        "scripts/run_study.py",
        "--output",
        "artifacts",
    )
    if completed.returncode != 0:
        return False
    try:
        results = json.loads((workspace / "artifacts/results.json").read_text())
        report = (workspace / "artifacts/report.md").read_text()
        input_digest = _sha256(workspace / "experiment.toml")
        return all(
            (
                math.isclose(
                    float(results["built_in_potential_v"]),
                    0.8333700106386042,
                    rel_tol=1.0e-10,
                ),
                math.isclose(
                    float(results["depletion_width_m"]),
                    1.4681182204823336e-7,
                    rel_tol=1.0e-10,
                ),
                math.isclose(
                    float(results["peak_electric_field_v_per_m"]),
                    11352900.590863995,
                    rel_tol=1.0e-10,
                ),
                abs(float(results["equilibrium_current_density_a_per_m2"]))
                <= 1.0e-20,
                input_digest in report,
                "analytic-equilibrium-v1" in report,
            )
        )
    except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
        return False


def _generalizes_beyond_reference(workspace: Path) -> bool:
    with tempfile.TemporaryDirectory(prefix="agent-kronig-repl-grade-") as temporary:
        temporary_root = Path(temporary)
        alternate_input = temporary_root / "alternate.toml"
        alternate_output = temporary_root / "artifacts"
        alternate_input.write_text(ALTERNATE_TOML)
        completed = _run(
            workspace,
            "scripts/run_study.py",
            "--input",
            str(alternate_input),
            "--output",
            str(alternate_output),
        )
        if completed.returncode != 0:
            return False
        try:
            results = json.loads((alternate_output / "results.json").read_text())
            return all(
                (
                    math.isclose(
                        float(results["built_in_potential_v"]),
                        0.8639924898708996,
                        rel_tol=1.0e-10,
                    ),
                    math.isclose(
                        float(results["depletion_width_m"]),
                        1.6712910398647097e-7,
                        rel_tol=1.0e-10,
                    ),
                    math.isclose(
                        float(results["peak_electric_field_v_per_m"]),
                        10339222.424609413,
                        rel_tol=1.0e-10,
                    ),
                )
            )
        except (KeyError, OSError, TypeError, ValueError, json.JSONDecodeError):
            return False


def grade(workspace: Path) -> dict[str, object]:
    checks = {
        "generalizes_beyond_reference": _generalizes_beyond_reference(workspace),
        "protected_inputs": _protected_inputs_unchanged(workspace),
        "scientific_artifacts": _scientific_artifacts_pass(workspace),
        "visible_tests": _visible_tests_pass(workspace),
    }
    weights = {
        "protected_inputs": 25,
        "visible_tests": 25,
        "scientific_artifacts": 30,
        "generalizes_beyond_reference": 20,
    }
    score = sum(weight for name, weight in weights.items() if checks[name])
    return {"checks": checks, "passed": score == 100, "score": score}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    arguments = parser.parse_args()
    workspace = arguments.workspace.expanduser().resolve()
    if not workspace.is_dir():
        parser.error("workspace must be an existing directory")
    result = grade(workspace)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
