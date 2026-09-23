import pytest

from tcad_agent.recovery.models import (
    FailureKind,
    FailureRecord,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryBudget,
)
from tcad_agent.recovery.policy import RecoveryPolicy


@pytest.mark.parametrize(
    ("kind", "expected"),
    [
        (FailureKind.EXECUTION, RecoveryAction.STOP_AND_REPORT),
        (FailureKind.TIMEOUT, RecoveryAction.INCREASE_ITERATION_LIMIT),
        (FailureKind.NON_CONVERGENCE, RecoveryAction.REDUCE_BIAS_STEP),
        (FailureKind.MALFORMED_OUTPUT, RecoveryAction.STOP_AND_REPORT),
        (FailureKind.NONFINITE_RESULT, RecoveryAction.STOP_AND_REPORT),
        (FailureKind.CONSERVATION, RecoveryAction.REFINE_MESH),
        (FailureKind.PHYSICAL_SANITY, RecoveryAction.STOP_AND_REPORT),
    ],
)
def test_policy_selects_only_allowlisted_actions(
    kind: FailureKind, expected: RecoveryAction
) -> None:
    decision = RecoveryPolicy().decide(
        FailureRecord(kind=kind, evidence="injected"),
        (),
        RecoveryBudget(max_attempts=3),
    )
    assert decision.action is expected


def test_policy_advances_instead_of_repeating_an_action() -> None:
    history = (
        RecoveryAttempt(
            action=RecoveryAction.REDUCE_BIAS_STEP,
            failure=FailureKind.NON_CONVERGENCE,
            succeeded=False,
        ),
    )
    decision = RecoveryPolicy().decide(
        FailureRecord(kind=FailureKind.NON_CONVERGENCE, evidence="still diverging"),
        history,
        RecoveryBudget(max_attempts=3),
    )
    assert decision.action is RecoveryAction.INCREASE_ITERATION_LIMIT


def test_policy_stops_when_attempt_budget_is_exhausted() -> None:
    history = (
        RecoveryAttempt(
            action=RecoveryAction.REDUCE_BIAS_STEP,
            failure=FailureKind.NON_CONVERGENCE,
            succeeded=False,
        ),
    )
    decision = RecoveryPolicy().decide(
        FailureRecord(kind=FailureKind.NON_CONVERGENCE, evidence="still diverging"),
        history,
        RecoveryBudget(max_attempts=1),
    )
    assert decision.action is RecoveryAction.STOP_AND_REPORT
    assert decision.reason == "recovery budget exhausted"
