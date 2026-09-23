"""Typed, case-scoped conformance rules and outcomes."""

from enum import StrEnum
from typing import Literal

from pydantic import Field

from tcad_agent.domain.models import StrictModel


class ComparisonStatus(StrEnum):
    PASSED = "passed"
    WARNING = "warning"
    FAILED = "failed"
    NOT_APPLICABLE = "not_applicable"


class ComparisonRule(StrictModel):
    metric: Literal[
        "terminal_current_density",
        "terminal_current_conservation",
        "qualitative_direction",
        "built_in_potential",
        "field_extrema",
        "carrier_profile",
        "mesh_stability",
    ]
    relative_tolerance: float = Field(ge=0)
    absolute_tolerance: float = Field(ge=0)
    field: str | None = None
    unit: str | None = None
    points: tuple[float, ...] = ()
    applicable: bool = True


class MetricComparison(StrictModel):
    metric: str
    status: ComparisonStatus
    message: str
    devsim_value: float | None = None
    sentaurus_value: float | None = None


class ConformanceReport(StrictModel):
    overall: ComparisonStatus
    comparisons: tuple[MetricComparison, ...]
