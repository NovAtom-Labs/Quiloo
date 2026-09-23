"""Allowlisted recovery transitions with a hard attempt budget."""

from typing import ClassVar

from tcad_agent.recovery.models import (
    FailureKind,
    FailureRecord,
    RecoveryAction,
    RecoveryAttempt,
    RecoveryBudget,
    RecoveryDecision,
)


class RecoveryPolicy:
    _actions: ClassVar[dict[FailureKind, tuple[RecoveryAction, ...]]] = {
        FailureKind.EXECUTION: (RecoveryAction.STOP_AND_REPORT,),
        FailureKind.TIMEOUT: (RecoveryAction.INCREASE_ITERATION_LIMIT,),
        FailureKind.NON_CONVERGENCE: (
            RecoveryAction.REDUCE_BIAS_STEP,
            RecoveryAction.INCREASE_ITERATION_LIMIT,
            RecoveryAction.REFINE_MESH,
        ),
        FailureKind.MALFORMED_OUTPUT: (RecoveryAction.STOP_AND_REPORT,),
        FailureKind.NONFINITE_RESULT: (RecoveryAction.STOP_AND_REPORT,),
        FailureKind.CONSERVATION: (RecoveryAction.REFINE_MESH,),
        FailureKind.PHYSICAL_SANITY: (RecoveryAction.STOP_AND_REPORT,),
    }

    def decide(
        self,
        failure: FailureRecord,
        history: tuple[RecoveryAttempt, ...],
        budget: RecoveryBudget,
    ) -> RecoveryDecision:
        if len(history) >= budget.max_attempts:
            return RecoveryDecision(
                action=RecoveryAction.STOP_AND_REPORT,
                reason="recovery budget exhausted",
            )
        attempted = {attempt.action for attempt in history}
        for action in self._actions[failure.kind]:
            if action not in attempted:
                return RecoveryDecision(
                    action=action,
                    reason=f"approved action for {failure.kind.value}",
                )
        return RecoveryDecision(
            action=RecoveryAction.STOP_AND_REPORT,
            reason="no untried approved recovery action",
        )
