"""Request-to-bundle orchestration over deterministic TCAD boundaries."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import cast
from uuid import UUID, uuid4

from pydantic import JsonValue, ValidationError

from tcad_agent.adapters.registry import BackendBinding, get_backend
from tcad_agent.bundles.models import BundleInputs
from tcad_agent.bundles.writer import BundleWriter
from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.control.clarification import ClarificationGate
from tcad_agent.control.execution import build_plan, digest_plan, expected_bias_points
from tcad_agent.control.models import (
    ClarificationAnswer,
    ClarificationQuestion,
    RequestRecord,
    RequestState,
    RequestView,
    ResearchRequest,
)
from tcad_agent.control.store import ConcurrentTransitionError, RequestStore
from tcad_agent.domain.models import ExperimentSpec
from tcad_agent.events.ledger import EventLedger
from tcad_agent.events.models import RunEvent, RunEventKind
from tcad_agent.model_gateway.base import AgentContextPacket, AgentProposal, ModelGateway
from tcad_agent.recovery.models import RecoveryBudget
from tcad_agent.recovery.policy import RecoveryPolicy
from tcad_agent.runners.models import CompiledJob, RunBudget
from tcad_agent.validation.engine import ValidationEngine


class ControlServiceError(RuntimeError):
    pass


class PlanDigestMismatchError(ControlServiceError):
    pass


class ExecutionNotApprovedError(ControlServiceError):
    pass


class InvalidRequestStateError(ControlServiceError):
    pass


def _json_object(value: object) -> dict[str, JsonValue]:
    decoded: object = json.loads(json.dumps(value))
    if not isinstance(decoded, dict):
        raise TypeError("expected a JSON object")
    return cast(dict[str, JsonValue], decoded)


def _json_array(value: object) -> list[JsonValue]:
    decoded: object = json.loads(json.dumps(value))
    if not isinstance(decoded, list):
        raise TypeError("expected a JSON array")
    return cast(list[JsonValue], decoded)


def _string_mapping(value: JsonValue) -> dict[str, str]:
    if not isinstance(value, dict):
        return {}
    return {str(key): str(item) for key, item in value.items()}


def _string_tuple(value: JsonValue) -> tuple[str, ...]:
    if not isinstance(value, list):
        return ()
    return tuple(str(item) for item in value)


class ControlService:
    def __init__(
        self,
        *,
        store: RequestStore,
        gateway: ModelGateway,
        workspace: Path,
        backend_resolver: Callable[[str], BackendBinding] = get_backend,
        run_budget_seconds: float = 120.0,
    ) -> None:
        self.store = store
        self.gateway = gateway
        self.workspace = workspace
        self.backend_resolver = backend_resolver
        self.run_budget_seconds = run_budget_seconds
        self.clarifications = ClarificationGate()
        self.workspace.mkdir(parents=True, exist_ok=True)

    def submit(self, prompt: str, *, backend: str = "devsim") -> RequestView:
        record = self.store.create(ResearchRequest(prompt=prompt))
        ledger = self._ledger(record.id)
        ledger.append(RunEventKind.REQUESTED, {"backend": backend})
        answers: dict[str, str] = {}
        questions = self.clarifications.required_questions(prompt, answers)
        warnings = self._context_warnings()
        if questions:
            record = self.store.transition(
                record.id,
                record.revision,
                RequestState.NEEDS_CLARIFICATION,
                {
                    "backend": backend,
                    "questions": _json_array(
                        [question.model_dump(mode="json") for question in questions]
                    ),
                    "answers": _json_object(answers),
                    "warnings": list(warnings),
                },
            )
            ledger.append(
                RunEventKind.CLARIFICATION_REQUIRED,
                {"fields": [question.field for question in questions]},
            )
            return self._view(record)
        record = self.store.transition(
            record.id,
            record.revision,
            RequestState.SPEC_DRAFTED,
            {"backend": backend, "warnings": list(warnings)},
        )
        return self._apply_proposal(record, self._propose(record))

    def answer(
        self,
        request_id: UUID,
        answers: tuple[ClarificationAnswer, ...],
    ) -> RequestView:
        record = self.store.get(request_id)
        if record.state is not RequestState.NEEDS_CLARIFICATION:
            raise InvalidRequestStateError("request is not waiting for clarification")
        combined = _string_mapping(record.data.get("answers"))
        combined.update({answer.field: answer.value for answer in answers})
        questions = self.clarifications.required_questions(record.request.prompt, combined)
        if questions:
            updated = self.store.transition(
                record.id,
                record.revision,
                RequestState.NEEDS_CLARIFICATION,
                {
                    "answers": _json_object(combined),
                    "questions": _json_array(
                        [question.model_dump(mode="json") for question in questions]
                    ),
                },
            )
            return self._view(updated)
        drafted = self.store.transition(
            record.id,
            record.revision,
            RequestState.SPEC_DRAFTED,
            {"answers": _json_object(combined), "questions": []},
        )
        return self._apply_proposal(drafted, self._propose(drafted))

    def approve(self, request_id: UUID, plan_digest: str) -> RequestView:
        record = self.store.get(request_id)
        stored_digest = str(record.data.get("plan_digest", ""))
        if not stored_digest or plan_digest != stored_digest:
            raise PlanDigestMismatchError("approval does not match the current plan digest")
        if record.state in {
            RequestState.COMPILED,
            RequestState.RUNNING,
            RequestState.VALIDATING,
            RequestState.COMPLETED,
        }:
            return self._view(record)
        if record.state is not RequestState.USER_CONFIRMATION_REQUIRED:
            raise InvalidRequestStateError("request is not ready for approval")
        spec = ExperimentSpec.model_validate(record.data["spec"])
        backend = str(record.data["backend"])
        binding = self.backend_resolver(backend)
        request_root = self._request_root(record.id)
        job = binding.adapter.compile(spec, request_root / "compiled")
        self._ledger(record.id).append(RunEventKind.APPROVED, {"plan_digest": plan_digest})
        self._ledger(record.id).append(RunEventKind.COMPILED, {"backend": backend})
        updated = self.store.transition(
            record.id,
            record.revision,
            RequestState.COMPILED,
            {
                "job": _json_object(job.model_dump(mode="json")),
                "run_id": f"run-{uuid4().hex[:12]}",
            },
        )
        return self._view(updated)

    def execute(self, request_id: UUID) -> RequestView:
        record = self.store.get(request_id)
        if record.state in {
            RequestState.RUNNING,
            RequestState.VALIDATING,
            RequestState.COMPLETED,
        }:
            return self._view(record)
        if record.state is not RequestState.COMPILED:
            raise ExecutionNotApprovedError("execution requires an approved compiled plan")
        try:
            running = self.store.transition(
                record.id,
                record.revision,
                RequestState.RUNNING,
                {},
            )
        except ConcurrentTransitionError:
            return self._view(self.store.get(request_id))
        ledger = self._ledger(request_id)
        ledger.append(RunEventKind.STARTED, {"backend": str(running.data["backend"])})
        backend = str(running.data["backend"])
        binding = self.backend_resolver(backend)
        spec = ExperimentSpec.model_validate(running.data["spec"])
        job = CompiledJob.model_validate(running.data["job"])
        native = binding.runner.run(job, RunBudget(seconds=self.run_budget_seconds))
        result = binding.adapter.normalize(native)
        validating = self.store.transition(
            running.id,
            running.revision,
            RequestState.VALIDATING,
            {
                "native": _json_object(native.model_dump(mode="json")),
                "result": _json_object(result.model_dump(mode="json")),
            },
        )
        validation_engine = ValidationEngine()
        validation = validation_engine.validate(
            result,
            expected_bias_points=expected_bias_points(spec),
        )
        failures = validation_engine.classify_failures(result)
        recovery: dict[str, JsonValue] | None = None
        if failures:
            decision = RecoveryPolicy().decide(
                failures[0], (), RecoveryBudget(max_attempts=0)
            )
            recovery = _json_object(decision.model_dump(mode="json"))
        terminal = (
            RunEventKind.COMPLETED
            if validation.overall == "passed"
            else RunEventKind.FAILED
        )
        ledger.append(
            terminal,
            {
                "execution_status": native.status,
                "validation_status": validation.overall,
            },
        )
        bundle = BundleWriter(self.workspace / "bundles").write(
            BundleInputs(
                run_id=str(validating.data["run_id"]),
                spec=spec,
                job=job,
                native=native,
                result=result,
                validation=validation,
                events_path=ledger.path,
            )
        )
        state = (
            RequestState.COMPLETED
            if validation.overall == "passed"
            else RequestState.FAILED
        )
        data: dict[str, JsonValue] = {
            "validation": _json_object(validation.model_dump(mode="json")),
            "bundle_path": str(bundle.root),
        }
        if recovery is not None:
            data["recovery"] = recovery
        if state is RequestState.FAILED:
            failure_code = failures[0].kind.value if failures else "validation_failed"
            data.update(
                {
                    "error_code": failure_code,
                    "error_message": "Simulator result failed deterministic validation.",
                }
            )
        finished = self.store.transition(
            validating.id,
            validating.revision,
            state,
            data,
        )
        return self._view(finished)

    def get(self, request_id: UUID) -> RequestView:
        return self._view(self.store.get(request_id))

    def events(self, request_id: UUID) -> tuple[RunEvent, ...]:
        self.store.get(request_id)
        return self._ledger(request_id).verify()

    def _apply_proposal(self, record: RequestRecord, proposal: AgentProposal) -> RequestView:
        ledger = self._ledger(record.id)
        if proposal.kind == "refusal":
            failed = self.store.transition(
                record.id,
                record.revision,
                RequestState.FAILED,
                {"error_code": "model_refusal", "error_message": proposal.message},
            )
            ledger.append(RunEventKind.FAILED, {"code": "model_refusal"})
            return self._view(failed)
        if proposal.kind == "clarification":
            waiting = self.store.transition(
                record.id,
                record.revision,
                RequestState.NEEDS_CLARIFICATION,
                {
                    "questions": [
                        _json_object(question.model_dump(mode="json"))
                        for question in proposal.questions
                    ]
                },
            )
            return self._view(waiting)
        try:
            spec = ExperimentSpec.model_validate(proposal.spec)
        except ValidationError:
            failed = self.store.transition(
                record.id,
                record.revision,
                RequestState.FAILED,
                {
                    "error_code": "invalid_spec",
                    "error_message": "Model proposal failed ExperimentSpec validation.",
                },
            )
            ledger.append(RunEventKind.FAILED, {"code": "invalid_spec"})
            return self._view(failed)
        backend = str(record.data["backend"])
        decision = CapabilityService().check(spec, CapabilityManifest.from_backend(backend))
        if decision.status is not CapabilityStatus.SUPPORTED:
            failed = self.store.transition(
                record.id,
                record.revision,
                RequestState.FAILED,
                {
                    "spec": _json_object(spec.normalized()),
                    "error_code": decision.status.value,
                    "error_message": "Requested experiment is unsupported by this backend.",
                    "capability": _json_object(decision.model_dump(mode="json")),
                },
            )
            ledger.append(RunEventKind.FAILED, {"code": decision.status.value})
            return self._view(failed)
        validated = self.store.transition(
            record.id,
            record.revision,
            RequestState.SPEC_VALIDATED,
            {"spec": _json_object(spec.normalized())},
        )
        ledger.append(RunEventKind.SPEC_DRAFTED, {"name": spec.name})
        ledger.append(RunEventKind.VALIDATED, {"backend": backend})
        warnings = _string_tuple(validated.data.get("warnings"))
        plan = build_plan(spec, backend, warnings)
        plan_digest = digest_plan(plan)
        review = self.store.transition(
            validated.id,
            validated.revision,
            RequestState.USER_CONFIRMATION_REQUIRED,
            {"plan": plan, "plan_digest": plan_digest},
        )
        return self._view(review)

    def _propose(self, record: RequestRecord) -> AgentProposal:
        warnings = _string_tuple(record.data.get("warnings"))
        context = AgentContextPacket(
            citations=(),
            capabilities={"backend": str(record.data["backend"]), "warnings": list(warnings)},
        )
        return self.gateway.propose(record.request, context)

    def _context_warnings(self) -> tuple[str, ...]:
        index = self.workspace / "knowledge" / "knowledge.sqlite3"
        return () if index.is_file() else ("knowledge_index_missing",)

    def _view(self, record: RequestRecord) -> RequestView:
        question_data = record.data.get("questions")
        questions = (
            tuple(
                ClarificationQuestion.model_validate(item)
                for item in question_data
                if isinstance(item, dict)
            )
            if isinstance(question_data, list)
            else ()
        )
        spec_value = record.data.get("spec")
        plan_value = record.data.get("plan")
        validation_value = record.data.get("validation")
        return RequestView(
            id=record.id,
            state=record.state,
            revision=record.revision,
            backend=str(record.data.get("backend", "devsim")),
            questions=questions,
            plan_digest=(
                str(record.data["plan_digest"]) if "plan_digest" in record.data else None
            ),
            plan=dict(plan_value) if isinstance(plan_value, dict) else None,
            spec=dict(spec_value) if isinstance(spec_value, dict) else None,
            validation=(
                dict(validation_value) if isinstance(validation_value, dict) else None
            ),
            bundle_path=(
                str(record.data["bundle_path"]) if "bundle_path" in record.data else None
            ),
            warnings=_string_tuple(record.data.get("warnings")),
            error_code=(
                str(record.data["error_code"]) if "error_code" in record.data else None
            ),
            error_message=(
                str(record.data["error_message"])
                if "error_message" in record.data
                else None
            ),
        )

    def _request_root(self, request_id: UUID) -> Path:
        root = self.workspace / "requests" / str(request_id)
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _ledger(self, request_id: UUID) -> EventLedger:
        return EventLedger(self._request_root(request_id) / "events.jsonl")
