"""FastAPI surface for the local TCAD researcher workflow."""

from __future__ import annotations

import json
import os
from collections.abc import Sequence
from pathlib import Path
from typing import Literal, Protocol, cast
from uuid import UUID

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    RedirectResponse,
    Response,
    StreamingResponse,
)
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from tcad_agent.agent.runtime import OpenHandsRuntimeFactory
from tcad_agent.agent.supervisor import AgentSupervisor
from tcad_agent.control.models import (
    ClarificationAnswer,
    RequestView,
    ResearchRequest,
)
from tcad_agent.control.service import (
    ControlService,
    ControlServiceError,
    InvalidRequestStateError,
    PlanDigestMismatchError,
)
from tcad_agent.control.store import RequestNotFoundError, SqliteRequestStore
from tcad_agent.desktop.auth import (
    DesktopAuth,
    DesktopSessionMiddleware,
    DesktopShutdownGate,
    DesktopShutdownMiddleware,
)
from tcad_agent.events.models import RunEvent
from tcad_agent.ide.conversations import ConversationInputError
from tcad_agent.ide.models import RunState
from tcad_agent.ide.paths import WorkspacePathError
from tcad_agent.ide.store import ConversationNotFoundError, WorkspaceNotFoundError
from tcad_agent.model_gateway.base import AgentContextPacket, AgentProposal, ModelGateway
from tcad_agent.model_gateway.openhands import (
    ModelConfigurationError,
    OpenHandsBedrockGateway,
)
from tcad_agent.web.ide_routes import (
    AgentAPIError,
    IDEServices,
    build_default_ide_services,
    build_ide_router,
)
from tcad_agent.web.runtime import runtime_fingerprint
from tcad_agent.web.schemas import (
    AnswerRequest,
    ApprovalRequest,
    CreateResearchRequest,
    ResearchResults,
)


class UnavailableGateway:
    def __init__(self, message: str) -> None:
        self.message = message

    def propose(
        self, request: ResearchRequest, context: AgentContextPacket
    ) -> AgentProposal:
        del request, context
        raise ModelConfigurationError(self.message)


class ControlAPI(Protocol):
    def submit(self, prompt: str, *, backend: str = "devsim") -> RequestView: ...

    def answer(
        self, request_id: UUID, answers: Sequence[ClarificationAnswer]
    ) -> RequestView: ...

    def approve(self, request_id: UUID, plan_digest: str) -> RequestView: ...

    def execute(self, request_id: UUID) -> RequestView: ...

    def get(self, request_id: UUID) -> RequestView: ...

    def events(self, request_id: UUID) -> tuple[RunEvent, ...]: ...


def build_default_control() -> ControlService:
    workspace = Path(os.getenv("TCAD_WORKSPACE", Path.cwd() / ".tcad-agent")).resolve()
    try:
        gateway: ModelGateway = OpenHandsBedrockGateway.from_environment()
    except ModelConfigurationError as exc:
        gateway = UnavailableGateway(str(exc))
    return ControlService(
        store=SqliteRequestStore(workspace / "requests.sqlite3"),
        gateway=gateway,
        workspace=workspace,
    )


def create_app(
    control: ControlAPI | None = None,
    *,
    runtime_id: str | None = None,
    ide: IDEServices | None = None,
    agent_supervisor: AgentSupervisor | None = None,
    desktop_auth: DesktopAuth | None = None,
) -> FastAPI:
    service = control or build_default_control()
    ide_services = ide or build_default_ide_services()
    active_supervisor = agent_supervisor or AgentSupervisor(
        ide_services, OpenHandsRuntimeFactory(ide_services.runtime_root)
    )
    active_runtime_id = runtime_id or runtime_fingerprint()
    package_root = Path(__file__).parent
    templates = Jinja2Templates(directory=package_root / "templates")
    app = FastAPI(title="NovAtom TCAD Agent", docs_url=None, redoc_url=None)
    shutdown_gate = DesktopShutdownGate()
    if desktop_auth is not None:
        app.add_middleware(DesktopShutdownMiddleware, gate=shutdown_gate)
        app.add_middleware(DesktopSessionMiddleware, auth=desktop_auth)
    app.mount("/static", StaticFiles(directory=package_root / "static"), name="static")
    app.include_router(build_ide_router(ide_services, active_supervisor))

    @app.exception_handler(AgentAPIError)
    async def agent_api_error(
        _request: Request, exc: AgentAPIError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": exc.message},
        )

    @app.exception_handler(WorkspacePathError)
    async def invalid_workspace_path(
        _request: Request, _exc: WorkspacePathError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "code": "invalid_workspace_path",
                "message": "The workspace path is unavailable or invalid.",
            },
        )

    @app.exception_handler(ConversationInputError)
    async def invalid_conversation_input(
        _request: Request, exc: ConversationInputError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={"code": "invalid_conversation_input", "message": str(exc)},
        )

    @app.exception_handler(WorkspaceNotFoundError)
    async def workspace_not_found(
        _request: Request, _exc: WorkspaceNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "code": "workspace_not_found",
                "message": "The workspace was not found.",
            },
        )

    @app.exception_handler(ConversationNotFoundError)
    async def conversation_not_found(
        _request: Request, _exc: ConversationNotFoundError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "code": "conversation_not_found",
                "message": "The conversation was not found.",
            },
        )

    @app.exception_handler(RequestNotFoundError)
    async def request_not_found(_request: Request, _exc: RequestNotFoundError) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={"code": "request_not_found", "message": "The request was not found."},
        )

    @app.exception_handler(PlanDigestMismatchError)
    async def plan_mismatch(_request: Request, _exc: PlanDigestMismatchError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"code": "plan_digest_mismatch", "message": "The approved plan changed."},
        )

    @app.exception_handler(InvalidRequestStateError)
    @app.exception_handler(ControlServiceError)
    async def invalid_state(_request: Request, exc: ControlServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=409,
            content={"code": "invalid_request_state", "message": str(exc)},
        )

    @app.exception_handler(ModelConfigurationError)
    async def model_configuration(
        _request: Request, _exc: ModelConfigurationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=503,
            content={
                "code": "model_configuration_error",
                "message": "The configured Bedrock model is unavailable. Check local credentials.",
            },
        )

    @app.exception_handler(Exception)
    async def internal_error(_request: Request, _exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content={
                "code": "internal_error",
                "message": (
                    "The request failed without exposing provider or credential details."
                ),
            },
        )

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "runtime_fingerprint": active_runtime_id}

    def has_active_work() -> bool:
        active_states = {
            RunState.QUEUED,
            RunState.RUNNING,
        }
        return bool(ide_services.store.list_runs_in_states(active_states)) or bool(
            getattr(service, "has_active_work", lambda: False)()
        )

    @app.get("/api/desktop/status")
    def desktop_status() -> dict[str, bool]:
        return {"active": has_active_work()}

    @app.post("/api/desktop/prepare-shutdown")
    def desktop_prepare_shutdown(request: Request) -> JSONResponse:
        if desktop_auth is None:
            raise HTTPException(status_code=404, detail="Desktop mode is unavailable.")
        authorization = request.headers.get("authorization", "")
        scheme, _, candidate = authorization.partition(" ")
        if scheme.lower() != "bearer" or not desktop_auth.is_control_token(candidate):
            return JSONResponse(
                status_code=403,
                content={
                    "code": "desktop_control_required",
                    "message": "Desktop lifecycle authentication failed.",
                },
            )
        if not shutdown_gate.commit_if_idle(has_active_work):
            return JSONResponse(
                status_code=409,
                content={
                    "code": "desktop_work_active",
                    "message": "Finish or stop active work before closing Agent Kronig.",
                },
            )
        return JSONResponse(content={"ready": True})

    @app.get("/desktop/bootstrap")
    def desktop_bootstrap(request: Request) -> Response:
        if desktop_auth is None:
            raise HTTPException(status_code=404, detail="Desktop mode is unavailable.")
        token = request.query_params.get("token", "")
        if not desktop_auth.consume_launch_token(token):
            raise HTTPException(status_code=403, detail="Invalid desktop launch token.")
        response = RedirectResponse("/", status_code=303)
        desktop_auth.attach_session(response)
        return response

    @app.get("/")
    def index(request: Request) -> Response:
        return templates.TemplateResponse(request, "ide.html", {})

    @app.get("/workspaces/{workspace_id}")
    def workspace_page(request: Request, workspace_id: UUID) -> Response:
        del workspace_id
        return templates.TemplateResponse(request, "ide.html", {})

    @app.get("/workspaces/{workspace_id}/conversations/{conversation_id}")
    def conversation_page(
        request: Request, workspace_id: UUID, conversation_id: UUID
    ) -> Response:
        del workspace_id, conversation_id
        return templates.TemplateResponse(request, "ide.html", {})

    @app.get("/simulate")
    def simulation_page() -> RedirectResponse:
        return RedirectResponse("/")

    @app.get("/requests/{request_id}/{stage}")
    def workflow_page(
        request: Request,
        request_id: UUID,
        stage: Literal["request", "clarify", "review", "results"],
    ) -> Response:
        del request, request_id, stage
        return RedirectResponse("/")

    @app.post("/api/requests", status_code=201)
    def create_request(payload: CreateResearchRequest) -> RequestView:
        return service.submit(payload.prompt, backend=payload.backend)

    @app.get("/api/requests/{request_id}")
    def get_request(request_id: UUID) -> RequestView:
        return service.get(request_id)

    @app.post("/api/requests/{request_id}/answers")
    def answer_request(request_id: UUID, payload: AnswerRequest) -> RequestView:
        return service.answer(request_id, payload.answers)

    @app.post("/api/requests/{request_id}/approve")
    def approve_request(request_id: UUID, payload: ApprovalRequest) -> RequestView:
        return service.approve(request_id, payload.plan_digest)

    @app.post("/api/requests/{request_id}/run")
    def run_request(request_id: UUID) -> RequestView:
        return service.execute(request_id)

    @app.get("/api/requests/{request_id}/results")
    def research_results(request_id: UUID) -> ResearchResults:
        view = service.get(request_id)
        if view.bundle_path is None:
            raise HTTPException(status_code=409, detail="results are not available")
        root = Path(view.bundle_path).resolve()

        def load_object(relative: str) -> dict[str, object]:
            path = (root / relative).resolve()
            if not path.is_relative_to(root) or not path.is_file():
                raise HTTPException(status_code=404, detail="result artifact is unavailable")
            value = json.loads(path.read_text())
            if not isinstance(value, dict):
                raise HTTPException(status_code=500, detail="result artifact is malformed")
            return cast(dict[str, object], value)

        return ResearchResults.model_validate(
            {
                "experiment": load_object("experiment.json"),
                "result": load_object("results/canonical.json"),
                "validation": load_object("validation/report.json"),
            }
        )

    @app.get("/api/requests/{request_id}/events")
    def request_events(request_id: UUID) -> StreamingResponse:
        events = service.events(request_id)
        rows = [
            "event: stage\ndata: "
            + json.dumps(event.model_dump(mode="json"), sort_keys=True)
            + "\n\n"
            for event in events
        ]
        return StreamingResponse(iter(rows), media_type="text/event-stream")

    @app.get("/api/requests/{request_id}/artifacts/{name:path}")
    def artifact(request_id: UUID, name: str) -> FileResponse:
        view = service.get(request_id)
        if view.bundle_path is None:
            raise HTTPException(status_code=404, detail="bundle is not available")
        if not name or Path(name).is_absolute() or ".." in Path(name).parts:
            raise HTTPException(status_code=400, detail="invalid artifact path")
        root = Path(view.bundle_path).resolve()
        manifest_path = root / "manifest.json"
        if not manifest_path.is_file():
            raise HTTPException(status_code=404, detail="bundle manifest is missing")
        manifest = json.loads(manifest_path.read_text())
        allowed = set(manifest.get("artifacts", {})) | {"manifest.json"}
        if name not in allowed:
            raise HTTPException(status_code=404, detail="artifact is not allowlisted")
        target = (root / name).resolve()
        if not target.is_relative_to(root) or not target.is_file():
            raise HTTPException(status_code=404, detail="artifact is unavailable")
        return FileResponse(target, filename=target.name)

    return app
