"""Validation evidence schema."""

from typing import Literal

from tcad_agent.domain.models import StrictModel

ValidationStatus = Literal["passed", "warning", "failed", "not_applicable"]


class ValidationCheck(StrictModel):
    id: str
    level: Literal["execution", "numerical", "physical", "provenance"]
    status: ValidationStatus
    measured_value: float | int | str | None = None
    limit: float | int | str | None = None
    message: str
    evidence_paths: tuple[str, ...] = ()


class ValidationReport(StrictModel):
    overall: ValidationStatus
    checks: tuple[ValidationCheck, ...]

    @property
    def checks_by_id(self) -> dict[str, ValidationCheck]:
        return {check.id: check for check in self.checks}
