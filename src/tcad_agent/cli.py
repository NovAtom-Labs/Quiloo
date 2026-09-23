"""Researcher-facing command line workflow."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Annotated
from uuid import uuid4

import typer
import yaml
from pydantic import ValidationError

from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.bundles.models import BundleInputs
from tcad_agent.bundles.writer import BundleWriter
from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.domain.models import DCStudy, ExperimentSpec
from tcad_agent.knowledge.retrieve import KnowledgeIndex
from tcad_agent.runners.local import LocalRunner
from tcad_agent.runners.models import RunBudget
from tcad_agent.validation.engine import ValidationEngine

app = typer.Typer(help="Validate, compile, run, and report simulator-neutral TCAD studies.")
knowledge_app = typer.Typer(help="Search the authorized versioned TCAD knowledge index.")
app.add_typer(knowledge_app, name="knowledge")

DEVSIM_PYTHON = Path("/Users/satyagni/Documents/NovAtom Labs/devsim/.venv/bin/python")
DEFAULT_COMPILED_OUTPUT = Path("compiled")
DEFAULT_RUN_OUTPUT = Path("runs")
DEFAULT_KNOWLEDGE_INDEX = Path("knowledge-sources/index/knowledge.sqlite3")


def _load_spec(path: Path) -> ExperimentSpec:
    try:
        payload = yaml.safe_load(path.read_text())
        return ExperimentSpec.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        typer.echo(f"invalid specification: {exc}", err=True)
        raise typer.Exit(2) from exc


def _require_backend(spec: ExperimentSpec, backend: str) -> CapabilityManifest:
    try:
        manifest = CapabilityManifest.from_backend(backend)
    except ValueError as exc:
        typer.echo(str(exc), err=True)
        raise typer.Exit(2) from exc
    decision = CapabilityService().check(spec, manifest)
    if decision.status is not CapabilityStatus.SUPPORTED:
        for issue in decision.issues:
            typer.echo(f"{issue.path}: {issue.message}", err=True)
        raise typer.Exit(2)
    if manifest.execution_state != "configured":
        typer.echo(f"{backend} runner is not configured", err=True)
        raise typer.Exit(2)
    return manifest


@app.command("validate")
def validate_command(spec_path: Path) -> None:
    """Validate a specification and print its normalized representation."""
    spec = _load_spec(spec_path)
    typer.echo(json.dumps(spec.normalized(), sort_keys=True, indent=2))


@app.command("compile")
def compile_command(
    spec_path: Path,
    backend: Annotated[str, typer.Option("--backend")] = "devsim",
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_COMPILED_OUTPUT,
) -> None:
    """Compile a supported specification without executing it."""
    spec = _load_spec(spec_path)
    _require_backend(spec, backend)
    if backend != "devsim":
        typer.echo(f"compiler unavailable for {backend}", err=True)
        raise typer.Exit(2)
    job = DevsimAdapter.from_defaults().compile(spec, output)
    typer.echo(json.dumps(job.model_dump(mode="json"), sort_keys=True, indent=2))


@app.command("run")
def run_command(
    spec_path: Path,
    backend: Annotated[str, typer.Option("--backend")] = "devsim",
    approve: Annotated[bool, typer.Option("--approve")] = False,
    output: Annotated[Path, typer.Option("--output")] = DEFAULT_RUN_OUTPUT,
    timeout_seconds: Annotated[float, typer.Option("--timeout-seconds")] = 120.0,
) -> None:
    """Run an explicitly approved experiment and create an evidence bundle."""
    if not approve:
        typer.echo("execution requires --approve", err=True)
        raise typer.Exit(2)
    spec = _load_spec(spec_path)
    _require_backend(spec, backend)
    if backend != "devsim":
        typer.echo(f"compiler unavailable for {backend}", err=True)
        raise typer.Exit(2)
    run_id = f"run-{uuid4().hex[:12]}"
    work = output / ".work" / run_id
    adapter = DevsimAdapter.from_defaults()
    job = adapter.compile(spec, work)
    native = LocalRunner(DEVSIM_PYTHON).run(job, RunBudget(seconds=timeout_seconds))
    result = adapter.normalize(native)
    expected_points = 1
    if isinstance(spec.study, DCStudy):
        expected_points = round(
            (spec.study.stop.to("V") - spec.study.start.to("V"))
            / spec.study.step.to("V")
        ) + 1
    validation = ValidationEngine().validate(result, expected_bias_points=expected_points)
    bundle = BundleWriter(output).write(
        BundleInputs(
            run_id=run_id,
            spec=spec,
            job=job,
            native=native,
            result=result,
            validation=validation,
        )
    )
    typer.echo(str(bundle.root))
    if bundle.state != "completed":
        raise typer.Exit(1)


@app.command("report")
def report_command(bundle: Path) -> None:
    """Print the deterministic Markdown report from a completed bundle."""
    report = bundle / "report.md"
    if not report.is_file():
        typer.echo(f"report not found: {report}", err=True)
        raise typer.Exit(2)
    typer.echo(report.read_text())


@knowledge_app.command("search")
def search_knowledge_command(
    query: str,
    index: Annotated[Path, typer.Option("--index")] = DEFAULT_KNOWLEDGE_INDEX,
    backend: Annotated[str | None, typer.Option("--backend")] = None,
    version: Annotated[str | None, typer.Option("--version")] = None,
    limit: Annotated[int, typer.Option("--limit")] = 5,
) -> None:
    """Search a prebuilt authorized knowledge index."""
    if not index.is_file():
        typer.echo(f"knowledge index not found: {index}", err=True)
        raise typer.Exit(2)
    filters = {
        key: value
        for key, value in {"backend": backend, "version": version}.items()
        if value is not None
    }
    hits = KnowledgeIndex(index).search(query, filters, limit)
    typer.echo(json.dumps([hit.model_dump(mode="json") for hit in hits], indent=2))
