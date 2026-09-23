"""Layered validators that do not depend on an LLM."""

from __future__ import annotations

import math

from tcad_agent.recovery.models import FailureKind, FailureRecord
from tcad_agent.results.models import CanonicalResult
from tcad_agent.validation.models import ValidationCheck, ValidationReport, ValidationStatus


class ValidationEngine:
    def __init__(self, current_rtol: float = 1e-4, current_atol: float = 1e-6) -> None:
        if current_rtol < 0 or current_atol < 0:
            raise ValueError("current tolerances must be nonnegative")
        self.current_rtol = current_rtol
        self.current_atol = current_atol

    def validate(
        self,
        result: CanonicalResult,
        *,
        expected_bias_points: int | None = None,
        require_provenance: bool = True,
    ) -> ValidationReport:
        checks: list[ValidationCheck] = []
        checks.append(
            self._check(
                "execution-status",
                "execution",
                result.status == "completed",
                result.status,
                "completed",
                "Simulator execution must complete before scientific validation.",
            )
        )
        has_points = bool(result.bias_points)
        checks.append(
            self._check(
                "bias-points-present",
                "numerical",
                has_points,
                len(result.bias_points),
                ">= 1",
                "At least one solved bias point is required.",
            )
        )
        if expected_bias_points is not None:
            checks.append(
                self._check(
                    "expected-point-count",
                    "numerical",
                    len(result.bias_points) == expected_bias_points,
                    len(result.bias_points),
                    expected_bias_points,
                    "Solved bias point count must match the approved study.",
                )
            )
        converged = all(point.converged for point in result.bias_points) and has_points
        checks.append(
            self._check(
                "all-points-converged",
                "numerical",
                converged,
                sum(point.converged for point in result.bias_points),
                len(result.bias_points),
                "Every returned bias point must converge.",
            )
        )
        finite = self._all_values_finite(result)
        checks.append(
            self._check(
                "finite-values",
                "numerical",
                finite,
                "finite" if finite else "non-finite",
                "finite",
                "Currents, biases, coordinates, and fields must contain finite numbers.",
            )
        )
        monotonic = all(
            right.bias_v >= left.bias_v
            for left, right in zip(result.bias_points, result.bias_points[1:], strict=False)
        )
        checks.append(
            self._check(
                "monotonic-bias",
                "numerical",
                monotonic,
                "monotonic" if monotonic else "non-monotonic",
                "monotonic",
                "Bias points must preserve the approved sweep order.",
            )
        )
        max_imbalance, max_limit = self._current_imbalance(result)
        checks.append(
            self._check(
                "terminal-current-conservation",
                "physical",
                max_imbalance <= max_limit and has_points,
                max_imbalance,
                max_limit,
                "The algebraic sum of terminal currents must satisfy the configured tolerance.",
            )
        )
        nonnegative = all(
            value >= 0
            for name, field in result.fields.items()
            if name in {"electron_density", "hole_density"}
            for value in field.values
        )
        checks.append(
            self._check(
                "nonnegative-carrier-density",
                "physical",
                nonnegative,
                "nonnegative" if nonnegative else "negative",
                ">= 0 m^-3",
                "Classical carrier densities cannot be negative.",
            )
        )
        if require_provenance:
            checks.append(
                self._check(
                    "simulator-version-recorded",
                    "provenance",
                    bool(result.simulator_version),
                    result.simulator_version or "missing",
                    "non-empty",
                    "A simulator version is required for reproducibility.",
                )
            )
        overall: ValidationStatus = "passed"
        if any(check.status == "failed" for check in checks):
            overall = "failed"
        elif any(check.status == "warning" for check in checks):
            overall = "warning"
        return ValidationReport(overall=overall, checks=tuple(checks))

    def classify_failures(self, result: CanonicalResult) -> tuple[FailureRecord, ...]:
        if result.status == "execution_failed":
            return (
                FailureRecord(
                    kind=FailureKind.EXECUTION,
                    evidence=result.error or result.status,
                ),
            )
        if result.status == "timed_out":
            return (
                FailureRecord(
                    kind=FailureKind.TIMEOUT,
                    evidence=result.error or result.status,
                ),
            )
        if result.status == "malformed_result":
            return (
                FailureRecord(
                    kind=FailureKind.MALFORMED_OUTPUT,
                    evidence=result.error or result.status,
                ),
            )

        failures: list[FailureRecord] = []
        if result.bias_points and not all(point.converged for point in result.bias_points):
            failures.append(
                FailureRecord(
                    kind=FailureKind.NON_CONVERGENCE,
                    evidence="one or more bias points did not converge",
                )
            )
        if not self._all_values_finite(result):
            failures.append(
                FailureRecord(
                    kind=FailureKind.NONFINITE_RESULT,
                    evidence="canonical result contains NaN or infinite values",
                )
            )
            return tuple(failures)

        report = self.validate(result)
        if report.checks_by_id["terminal-current-conservation"].status == "failed":
            failures.append(
                FailureRecord(
                    kind=FailureKind.CONSERVATION,
                    evidence="terminal current conservation check failed",
                )
            )
        if report.checks_by_id["nonnegative-carrier-density"].status == "failed":
            failures.append(
                FailureRecord(
                    kind=FailureKind.PHYSICAL_SANITY,
                    evidence="carrier density sanity check failed",
                )
            )
        return tuple(failures)

    def _current_imbalance(self, result: CanonicalResult) -> tuple[float, float]:
        worst_imbalance = 0.0
        worst_limit = self.current_atol
        for point in result.bias_points:
            currents = tuple(point.terminal_currents_a_per_m2.values())
            imbalance = abs(sum(currents))
            scale = max((abs(value) for value in currents), default=0.0)
            limit = self.current_atol + self.current_rtol * scale
            if imbalance > worst_imbalance:
                worst_imbalance = imbalance
                worst_limit = limit
        return worst_imbalance, worst_limit

    @staticmethod
    def _all_values_finite(result: CanonicalResult) -> bool:
        values: list[float] = []
        for point in result.bias_points:
            values.append(point.bias_v)
            values.extend(point.terminal_currents_a_per_m2.values())
        for field in result.fields.values():
            values.extend(field.positions_m)
            values.extend(field.values)
        return all(math.isfinite(value) for value in values)

    @staticmethod
    def _check(
        check_id: str,
        level: str,
        passed: bool,
        measured: float | int | str,
        limit: float | int | str,
        message: str,
    ) -> ValidationCheck:
        return ValidationCheck.model_validate(
            {
                "id": check_id,
                "level": level,
                "status": "passed" if passed else "failed",
                "measured_value": measured,
                "limit": limit,
                "message": message,
            }
        )
