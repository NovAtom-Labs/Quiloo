"""Typed tool operations exposed to the agent and CLI."""

from __future__ import annotations

import json
from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal
from uuid import uuid4

from openhands.sdk.tool import (
    Action,
    Observation,
    ToolAnnotations,
    ToolDefinition,
    ToolExecutor,
    register_tool,
)
from pydantic import Field, ValidationError

from tcad_agent.adapters.registry import BackendAdapterUnavailable, get_backend
from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.domain.errors import CapabilityError
from tcad_agent.domain.models import ExperimentSpec, StrictModel

if TYPE_CHECKING:
    from openhands.sdk.conversation import LocalConversation
    from openhands.sdk.conversation.state import ConversationState


class ToolResponse(StrictModel):
    status: Literal["ok", "refused", "error"]
    code: str
    message: str
    data: dict[str, object] = Field(default_factory=dict)


class DomainTools:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace.resolve()

    def validate_spec(self, payload: dict[str, object]) -> ToolResponse:
        try:
            spec = ExperimentSpec.model_validate(payload)
        except ValidationError as exc:
            return ToolResponse(
                status="refused",
                code="invalid_spec",
                message="Experiment specification failed schema or semantic validation.",
                data={"errors": exc.errors(include_url=False)},
            )
        return ToolResponse(
            status="ok",
            code="valid_spec",
            message="Experiment specification is valid.",
            data={"spec": spec.normalized()},
        )

    def compile_experiment(
        self, payload: dict[str, object], *, backend: str
    ) -> ToolResponse:
        validated = self.validate_spec(payload)
        if validated.status != "ok":
            return validated
        spec = ExperimentSpec.model_validate(payload)
        try:
            manifest = CapabilityManifest.from_backend(backend)
        except ValueError as exc:
            return ToolResponse(status="refused", code="unknown_backend", message=str(exc))
        decision = CapabilityService().check(spec, manifest)
        if decision.status is not CapabilityStatus.SUPPORTED:
            return ToolResponse(
                status="refused",
                code=decision.status,
                message="Requested experiment is unsupported by the selected backend.",
                data={"decision": decision.model_dump(mode="json")},
            )
        workspace = self.workspace / "compiled" / uuid4().hex
        try:
            job = get_backend(backend).adapter.compile(spec, workspace)
        except BackendAdapterUnavailable as exc:
            return ToolResponse(
                status="refused", code="compiler_unavailable", message=str(exc)
            )
        except CapabilityError as exc:
            return ToolResponse(status="refused", code="capability_error", message=str(exc))
        return ToolResponse(
            status="ok",
            code="compiled",
            message="Experiment compiled through the deterministic adapter.",
            data={"job": job.model_dump(mode="json")},
        )

    def run_experiment(self, request: dict[str, object]) -> ToolResponse:
        if not request.get("approved_plan_id"):
            return ToolResponse(
                status="refused",
                code="approval_required",
                message="Execution requires an approved plan identifier.",
            )
        return ToolResponse(
            status="refused",
            code="use_controlled_workflow",
            message="Execute approved jobs through the CLI or control service workflow.",
        )

    def validate_result(self, payload: dict[str, object]) -> ToolResponse:
        from tcad_agent.results.models import CanonicalResult
        from tcad_agent.validation.engine import ValidationEngine

        try:
            result = CanonicalResult.model_validate(payload)
        except ValidationError as exc:
            return ToolResponse(
                status="refused",
                code="invalid_result",
                message="Canonical result is invalid.",
                data={"errors": exc.errors(include_url=False)},
            )
        report = ValidationEngine().validate(result)
        return ToolResponse(
            status="ok" if report.overall == "passed" else "refused",
            code=f"validation_{report.overall}",
            message=f"Result validation completed with status {report.overall}.",
            data={"validation": report.model_dump(mode="json")},
        )

    def search_knowledge(
        self, query: str, filters: dict[str, str], limit: int = 5
    ) -> ToolResponse:
        from tcad_agent.knowledge.retrieve import KnowledgeIndex

        index_path = self.workspace / "knowledge-sources" / "index" / "knowledge.sqlite3"
        if not index_path.is_file():
            return ToolResponse(
                status="refused",
                code="knowledge_index_missing",
                message="Build the authorized knowledge index before retrieval.",
            )
        hits = KnowledgeIndex(index_path).search(query, filters, limit)
        return ToolResponse(
            status="ok",
            code="retrieved",
            message=f"Retrieved {len(hits)} passages.",
            data={"hits": [hit.model_dump(mode="json") for hit in hits]},
        )

    def build_report(self, payload: dict[str, object]) -> ToolResponse:
        from tcad_agent.reporting.markdown import MarkdownReport
        from tcad_agent.results.models import CanonicalResult
        from tcad_agent.validation.models import ValidationReport

        try:
            spec = ExperimentSpec.model_validate(payload["spec"])
            result = CanonicalResult.model_validate(payload["result"])
            validation = ValidationReport.model_validate(payload["validation"])
        except (KeyError, ValidationError) as exc:
            return ToolResponse(
                status="refused",
                code="invalid_report_inputs",
                message=f"Report inputs are invalid: {exc}",
            )
        report = MarkdownReport().render(spec, result, validation)
        return ToolResponse(
            status="ok",
            code="report_built",
            message="Report rendered from structured evidence.",
            data={"markdown": report},
        )


def build_tools(workspace: Path | None = None) -> DomainTools:
    return DomainTools(workspace or Path.cwd())


class TcadDomainAction(Action):
    operation: Literal[
        "validate_spec",
        "compile_experiment",
        "run_experiment",
        "validate_result",
        "search_knowledge",
        "build_report",
    ]
    payload: dict[str, Any] = Field(default_factory=dict)
    backend: str | None = None


class TcadDomainObservation(Observation):
    status: str
    code: str
    message: str
    data: dict[str, Any] = Field(default_factory=dict)


class TcadDomainExecutor(ToolExecutor[TcadDomainAction, TcadDomainObservation]):
    def __init__(self, workspace: Path) -> None:
        self.tools = build_tools(workspace)

    def __call__(
        self,
        action: TcadDomainAction,
        conversation: LocalConversation | None = None,
    ) -> TcadDomainObservation:
        if action.operation == "compile_experiment":
            response = self.tools.compile_experiment(
                action.payload, backend=action.backend or "devsim"
            )
        elif action.operation == "validate_spec":
            response = self.tools.validate_spec(action.payload)
        elif action.operation == "run_experiment":
            response = self.tools.run_experiment(action.payload)
        elif action.operation == "validate_result":
            response = self.tools.validate_result(action.payload)
        elif action.operation == "search_knowledge":
            response = self.tools.search_knowledge(
                str(action.payload.get("query", "")),
                action.payload.get("filters", {}),
                int(action.payload.get("limit", 5)),
            )
        else:
            response = self.tools.build_report(action.payload)
        return TcadDomainObservation(
            status=response.status,
            code=response.code,
            message=response.message,
            data=json.loads(response.model_dump_json())["data"],
            is_error=response.status == "error",
        )


class TcadDomainTool(ToolDefinition[TcadDomainAction, TcadDomainObservation]):
    name = "tcad_domain"

    @classmethod
    def create(
        cls, conv_state: ConversationState, **params: object
    ) -> Sequence[TcadDomainTool]:
        workspace = Path(conv_state.workspace.working_dir)
        return (
            cls(
                action_type=TcadDomainAction,
                observation_type=TcadDomainObservation,
                description=(
                    "Validate, compile, retrieve, validate results, and report "
                    "through typed TCAD boundaries."
                ),
                annotations=ToolAnnotations(
                    title="TCAD domain",
                    readOnlyHint=False,
                    destructiveHint=False,
                    idempotentHint=False,
                    openWorldHint=False,
                ),
                executor=TcadDomainExecutor(workspace),
            ),
        )


register_tool(TcadDomainTool.name, TcadDomainTool)
