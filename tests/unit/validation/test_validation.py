import math

from tcad_agent.recovery.models import FailureKind
from tcad_agent.results.models import BiasPoint, CanonicalResult
from tcad_agent.validation.engine import ValidationEngine


def canonical_result(
    *,
    anode_current: float = 1.0,
    cathode_current: float = -1.0,
    converged: bool = True,
    status: str = "completed",
    bias_points: tuple[BiasPoint, ...] | None = None,
) -> CanonicalResult:
    points = bias_points
    if points is None:
        points = (
            BiasPoint(
                bias_v=0.1,
                converged=converged,
                terminal_currents_a_per_m2={
                    "anode": anode_current,
                    "cathode": cathode_current,
                },
            ),
        )
    return CanonicalResult(
        backend="devsim",
        simulator_version="2.9.1",
        status=status,
        terminals=("anode", "cathode"),
        bias_points=points,
    )


def test_converged_but_nonconserving_result_fails_physical_validation() -> None:
    result = canonical_result(anode_current=1.0, cathode_current=-0.7, converged=True)
    report = ValidationEngine(current_rtol=1e-6).validate(result)
    assert report.overall == "failed"
    assert report.checks_by_id["terminal-current-conservation"].status == "failed"


def test_failed_process_cannot_be_validated_as_success() -> None:
    result = canonical_result(status="execution_failed", bias_points=())
    report = ValidationEngine().validate(result)
    assert report.overall == "failed"
    assert report.checks_by_id["execution-status"].status == "failed"


def test_valid_conserving_result_passes() -> None:
    report = ValidationEngine().validate(canonical_result())
    assert report.overall == "passed"


def test_classifies_execution_failure_without_secondary_noise() -> None:
    engine = ValidationEngine()
    failures = engine.classify_failures(
        canonical_result(status="execution_failed", bias_points=())
    )
    assert [failure.kind for failure in failures] == [FailureKind.EXECUTION]


def test_classifies_nonconvergence_nonfinite_and_conservation_separately() -> None:
    engine = ValidationEngine(current_rtol=1e-6)
    nonconverged = engine.classify_failures(canonical_result(converged=False))
    nonfinite = engine.classify_failures(canonical_result(anode_current=math.nan))
    nonconserving = engine.classify_failures(
        canonical_result(anode_current=1.0, cathode_current=-0.7)
    )
    assert [failure.kind for failure in nonconverged] == [FailureKind.NON_CONVERGENCE]
    assert [failure.kind for failure in nonfinite] == [FailureKind.NONFINITE_RESULT]
    assert [failure.kind for failure in nonconserving] == [FailureKind.CONSERVATION]


def test_validation_status_supports_not_applicable() -> None:
    from tcad_agent.validation.models import ValidationCheck

    check = ValidationCheck(
        id="mesh-refinement",
        level="numerical",
        status="not_applicable",
        message="No refined result was requested.",
    )
    assert check.status == "not_applicable"
