from pathlib import Path

from tcad_agent.conformance.compare import compare_results, load_case_rules
from tcad_agent.conformance.models import ComparisonRule, ComparisonStatus
from tcad_agent.results.models import BiasPoint, CanonicalResult, FieldSeries


def result(
    backend: str,
    *,
    current: float = 10.0,
    potential: tuple[float, ...] = (0.0, 0.3, 0.7),
) -> CanonicalResult:
    return CanonicalResult.model_validate(
        {
            "backend": backend,
            "simulator_version": "test",
            "status": "completed",
            "terminals": ["anode", "cathode"],
            "bias_points": [
                BiasPoint(
                    bias_v=0.1,
                    converged=True,
                    terminal_currents_a_per_m2={
                        "anode": current,
                        "cathode": -current,
                    },
                )
            ],
            "fields": {
                "potential": FieldSeries(
                    positions_m=(0.0, 1.0e-6, 2.0e-6),
                    values=potential,
                    unit="V",
                )
            },
        }
    )


def test_values_within_case_tolerance_pass() -> None:
    rules = (
        ComparisonRule(
            metric="terminal_current_density",
            relative_tolerance=0.1,
            absolute_tolerance=1.0e-9,
        ),
        ComparisonRule(
            metric="built_in_potential",
            field="potential",
            relative_tolerance=0.05,
            absolute_tolerance=1.0e-3,
        ),
    )
    report = compare_results(result("devsim"), result("sentaurus", current=10.5), rules)
    assert report.overall is ComparisonStatus.PASSED


def test_current_sign_reversal_fails_even_when_magnitude_matches() -> None:
    rule = ComparisonRule(
        metric="terminal_current_density",
        relative_tolerance=0.1,
        absolute_tolerance=1.0e-9,
    )
    report = compare_results(result("devsim"), result("sentaurus", current=-10.0), (rule,))
    assert report.comparisons[0].status is ComparisonStatus.FAILED
    assert "direction" in report.comparisons[0].message


def test_missing_required_field_fails() -> None:
    rule = ComparisonRule(
        metric="built_in_potential",
        field="electric_field",
        relative_tolerance=0.1,
        absolute_tolerance=1.0,
    )
    report = compare_results(result("devsim"), result("sentaurus"), (rule,))
    assert report.comparisons[0].status is ComparisonStatus.FAILED
    assert "missing" in report.comparisons[0].message


def test_explicitly_unsupported_rule_is_not_applicable() -> None:
    rule = ComparisonRule(
        metric="mesh_stability",
        relative_tolerance=0.1,
        absolute_tolerance=0.0,
        applicable=False,
    )
    report = compare_results(result("devsim"), result("sentaurus"), (rule,))
    assert report.comparisons[0].status is ComparisonStatus.NOT_APPLICABLE


def test_case_rules_load_reviewed_tolerances_from_yaml() -> None:
    rules = load_case_rules(
        Path("evaluations/conformance/cases.yaml"), "al-pn-al-equilibrium"
    )
    assert {rule.metric for rule in rules} >= {
        "built_in_potential",
        "field_extrema",
        "carrier_profile",
        "mesh_stability",
    }
