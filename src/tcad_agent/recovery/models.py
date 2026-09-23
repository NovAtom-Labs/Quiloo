"""Typed recovery records that can be persisted in an experiment ledger."""

from enum import StrEnum

from pydantic import Field

from tcad_agent.domain.models import StrictModel


class FailureKind(StrEnum):
    EXECUTION = "execution"
    TIMEOUT = "timeout"
    NON_CONVERGENCE = "non_convergence"
    MALFORMED_OUTPUT = "malformed_output"
    NONFINITE_RESULT = "nonfinite_result"
    CONSERVATION = "conservation"
    PHYSICAL_SANITY = "physical_sanity"


class RecoveryAction(StrEnum):
    REDUCE_BIAS_STEP = "reduce_bias_step"
    INCREASE_ITERATION_LIMIT = "increase_iteration_limit"
    REFINE_MESH = "refine_mesh"
    STOP_AND_REPORT = "stop_and_report"


class FailureRecord(StrictModel):
    kind: FailureKind
    evidence: str = Field(min_length=1)


class RecoveryAttempt(StrictModel):
    action: RecoveryAction
    failure: FailureKind
    succeeded: bool


class RecoveryBudget(StrictModel):
    max_attempts: int = Field(ge=0, le=10)


class RecoveryDecision(StrictModel):
    action: RecoveryAction
    reason: str = Field(min_length=1)

    @property
    def should_retry(self) -> bool:
        return self.action is not RecoveryAction.STOP_AND_REPORT
