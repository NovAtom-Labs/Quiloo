"""Canonical result schema consumed by validation and reporting."""

from pathlib import Path
from typing import Literal

from pydantic import Field

from tcad_agent.domain.models import StrictModel


class BiasPoint(StrictModel):
    bias_v: float
    converged: bool
    terminal_currents_a_per_m2: dict[str, float]


class FieldSeries(StrictModel):
    positions_m: tuple[float, ...]
    values: tuple[float, ...]
    unit: str


class CanonicalResult(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    backend: Literal["devsim", "sentaurus"]
    simulator_version: str | None = None
    status: Literal["completed", "execution_failed", "timed_out", "malformed_result"]
    terminals: tuple[str, ...] = ()
    bias_points: tuple[BiasPoint, ...] = ()
    fields: dict[str, FieldSeries] = Field(default_factory=dict)
    native_result_path: Path | None = None
    error: str | None = None

