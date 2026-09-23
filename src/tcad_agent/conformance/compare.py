"""Deterministic comparison using only expert-reviewed per-case tolerances."""

from __future__ import annotations

import math
from collections.abc import Sequence
from pathlib import Path

import yaml

from tcad_agent.conformance.models import (
    ComparisonRule,
    ComparisonStatus,
    ConformanceReport,
    MetricComparison,
)
from tcad_agent.results.models import BiasPoint, CanonicalResult, FieldSeries


def load_case_rules(path: Path, case_id: str) -> tuple[ComparisonRule, ...]:
    payload = yaml.safe_load(path.read_text())
    if not isinstance(payload, dict) or not isinstance(payload.get("cases"), list):
        raise ValueError("conformance case file is invalid")
    case = next(
        (
            item
            for item in payload["cases"]
            if isinstance(item, dict) and item.get("id") == case_id
        ),
        None,
    )
    if case is None or not isinstance(case.get("compare"), list):
        raise ValueError(f"conformance case {case_id!r} was not found")
    return tuple(ComparisonRule.model_validate(item) for item in case["compare"])


def _close(left: float, right: float, rule: ComparisonRule) -> bool:
    return math.isclose(
        left,
        right,
        rel_tol=rule.relative_tolerance,
        abs_tol=rule.absolute_tolerance,
    )


def _failure(rule: ComparisonRule, message: str) -> MetricComparison:
    return MetricComparison(
        metric=rule.metric,
        status=ComparisonStatus.FAILED,
        message=message,
    )


def _bias_point(result: CanonicalResult, bias: float) -> BiasPoint | None:
    return next(
        (point for point in result.bias_points if math.isclose(point.bias_v, bias, abs_tol=1e-12)),
        None,
    )


def _terminal_value(result: CanonicalResult, point: BiasPoint) -> float | None:
    terminal = result.terminals[0] if result.terminals else None
    if terminal is None and point.terminal_currents_a_per_m2:
        terminal = sorted(point.terminal_currents_a_per_m2)[0]
    if terminal is None:
        return None
    return point.terminal_currents_a_per_m2.get(terminal)


def _compare_current(
    devsim: CanonicalResult, sentaurus: CanonicalResult, rule: ComparisonRule
) -> MetricComparison:
    biases = rule.points or tuple(point.bias_v for point in devsim.bias_points)
    if not biases:
        return _failure(rule, "current comparison has no bias points")
    worst_left = 0.0
    worst_right = 0.0
    for bias in biases:
        left_point = _bias_point(devsim, bias)
        right_point = _bias_point(sentaurus, bias)
        if left_point is None or right_point is None:
            return _failure(rule, f"missing current at bias {bias:g} V")
        left = _terminal_value(devsim, left_point)
        right = _terminal_value(sentaurus, right_point)
        if left is None or right is None:
            return _failure(rule, "missing terminal current")
        if (
            abs(left) > rule.absolute_tolerance
            and abs(right) > rule.absolute_tolerance
            and math.copysign(1.0, left) != math.copysign(1.0, right)
        ):
            return _failure(rule, f"current direction differs at bias {bias:g} V")
        worst_left, worst_right = left, right
        if not _close(left, right, rule):
            return MetricComparison(
                metric=rule.metric,
                status=ComparisonStatus.FAILED,
                message=f"current differs beyond the case tolerance at bias {bias:g} V",
                devsim_value=left,
                sentaurus_value=right,
            )
    return MetricComparison(
        metric=rule.metric,
        status=ComparisonStatus.PASSED,
        message="terminal currents agree within the case tolerance",
        devsim_value=worst_left,
        sentaurus_value=worst_right,
    )


def _conservation_error(result: CanonicalResult) -> float | None:
    if not result.bias_points:
        return None
    errors: list[float] = []
    for point in result.bias_points:
        currents = tuple(point.terminal_currents_a_per_m2.values())
        if not currents:
            return None
        scale = max(max(abs(value) for value in currents), 1.0e-300)
        errors.append(abs(sum(currents)) / scale)
    return max(errors)


def _compare_conservation(
    devsim: CanonicalResult, sentaurus: CanonicalResult, rule: ComparisonRule
) -> MetricComparison:
    left = _conservation_error(devsim)
    right = _conservation_error(sentaurus)
    if left is None or right is None:
        return _failure(rule, "missing terminal currents for conservation")
    limit = max(rule.relative_tolerance, rule.absolute_tolerance)
    status = ComparisonStatus.PASSED if max(left, right) <= limit else ComparisonStatus.FAILED
    return MetricComparison(
        metric=rule.metric,
        status=status,
        message=(
            "both backends satisfy current conservation"
            if status is ComparisonStatus.PASSED
            else "at least one backend violates current conservation"
        ),
        devsim_value=left,
        sentaurus_value=right,
    )


def _field(
    result: CanonicalResult, rule: ComparisonRule
) -> tuple[FieldSeries | None, MetricComparison | None]:
    if rule.field is None:
        return None, _failure(rule, "comparison rule does not name a field")
    field = result.fields.get(rule.field)
    if field is None:
        return None, _failure(rule, f"missing required field {rule.field!r}")
    return field, None


def _scalar_field_metric(
    devsim: CanonicalResult,
    sentaurus: CanonicalResult,
    rule: ComparisonRule,
    reducer: str,
) -> MetricComparison:
    left_field, error = _field(devsim, rule)
    if error is not None:
        return error
    right_field, error = _field(sentaurus, rule)
    if error is not None:
        return error
    assert left_field is not None and right_field is not None
    if left_field.unit != right_field.unit:
        return _failure(rule, "field units differ after normalization")
    if reducer == "range":
        left = max(left_field.values) - min(left_field.values)
        right = max(right_field.values) - min(right_field.values)
    else:
        left = max(abs(value) for value in left_field.values)
        right = max(abs(value) for value in right_field.values)
    status = ComparisonStatus.PASSED if _close(left, right, rule) else ComparisonStatus.FAILED
    return MetricComparison(
        metric=rule.metric,
        status=status,
        message=(
            "field metric agrees within the case tolerance"
            if status is ComparisonStatus.PASSED
            else "field metric differs beyond the case tolerance"
        ),
        devsim_value=left,
        sentaurus_value=right,
    )


def _profile_metric(
    devsim: CanonicalResult, sentaurus: CanonicalResult, rule: ComparisonRule
) -> MetricComparison:
    left_field, error = _field(devsim, rule)
    if error is not None:
        return error
    right_field, error = _field(sentaurus, rule)
    if error is not None:
        return error
    assert left_field is not None and right_field is not None
    if left_field.unit != right_field.unit:
        return _failure(rule, "profile units differ after normalization")
    if len(left_field.values) != len(right_field.values):
        return MetricComparison(
            metric=rule.metric,
            status=ComparisonStatus.WARNING,
            message="profile meshes differ and require reviewed interpolation",
        )
    for left, right in zip(left_field.values, right_field.values, strict=True):
        if not _close(left, right, rule):
            return _failure(rule, "carrier profile differs beyond the case tolerance")
    return MetricComparison(
        metric=rule.metric,
        status=ComparisonStatus.PASSED,
        message="carrier profile agrees within the case tolerance",
    )


def compare_results(
    devsim: CanonicalResult,
    sentaurus: CanonicalResult,
    rules: Sequence[ComparisonRule],
) -> ConformanceReport:
    comparisons: list[MetricComparison] = []
    for rule in rules:
        if not rule.applicable:
            comparisons.append(
                MetricComparison(
                    metric=rule.metric,
                    status=ComparisonStatus.NOT_APPLICABLE,
                    message="comparison is explicitly not applicable for this case",
                )
            )
        elif devsim.status != "completed" or sentaurus.status != "completed":
            comparisons.append(_failure(rule, "both backend runs must be completed"))
        elif rule.metric in {"terminal_current_density", "qualitative_direction"}:
            comparisons.append(_compare_current(devsim, sentaurus, rule))
        elif rule.metric == "terminal_current_conservation":
            comparisons.append(_compare_conservation(devsim, sentaurus, rule))
        elif rule.metric == "built_in_potential":
            comparisons.append(_scalar_field_metric(devsim, sentaurus, rule, "range"))
        elif rule.metric == "field_extrema":
            comparisons.append(_scalar_field_metric(devsim, sentaurus, rule, "extrema"))
        elif rule.metric == "carrier_profile":
            comparisons.append(_profile_metric(devsim, sentaurus, rule))
        else:
            comparisons.append(
                MetricComparison(
                    metric=rule.metric,
                    status=ComparisonStatus.NOT_APPLICABLE,
                    message="mesh stability requires paired coarse and refined runs",
                )
            )
    statuses = {item.status for item in comparisons}
    if ComparisonStatus.FAILED in statuses:
        overall = ComparisonStatus.FAILED
    elif ComparisonStatus.WARNING in statuses:
        overall = ComparisonStatus.WARNING
    elif ComparisonStatus.PASSED in statuses:
        overall = ComparisonStatus.PASSED
    else:
        overall = ComparisonStatus.NOT_APPLICABLE
    return ConformanceReport(overall=overall, comparisons=tuple(comparisons))
