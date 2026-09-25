"""One-use bootstrap authentication for the private desktop webview."""

from __future__ import annotations

import secrets
import threading
from collections.abc import Callable

from fastapi import Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint

DESKTOP_SESSION_COOKIE = "agent_kronig_desktop_session"


class DesktopAuth:
    """Exchange one launch token for one in-memory desktop session."""

    def __init__(self, launch_token: str) -> None:
        if len(launch_token.encode("utf-8")) < 32:
            raise ValueError("desktop launch token must contain at least 32 bytes")
        self._launch_token = launch_token
        self._session_token = secrets.token_urlsafe(32)
        self._consumed = False
        self._guard = threading.Lock()

    def consume_launch_token(self, candidate: str) -> bool:
        with self._guard:
            if self._consumed or len(candidate.encode("utf-8")) < 32:
                return False
            accepted = secrets.compare_digest(candidate, self._launch_token)
            if accepted:
                self._consumed = True
            return accepted

    def is_authenticated(self, request: Request) -> bool:
        candidate = request.cookies.get(DESKTOP_SESSION_COOKIE, "")
        return bool(candidate) and secrets.compare_digest(
            candidate, self._session_token
        )

    def is_control_token(self, candidate: str) -> bool:
        """Authenticate a shell-only lifecycle request."""

        return bool(candidate) and secrets.compare_digest(
            candidate, self._launch_token
        )

    def attach_session(self, response: Response) -> None:
        response.set_cookie(
            DESKTOP_SESSION_COOKIE,
            self._session_token,
            httponly=True,
            samesite="strict",
            secure=False,
            path="/",
        )


class DesktopSessionMiddleware(BaseHTTPMiddleware):
    """Reject every non-bootstrap request without the desktop session."""

    def __init__(self, app: object, auth: DesktopAuth) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.auth = auth

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        if request.url.path in {
            "/health",
            "/desktop/bootstrap",
            "/api/desktop/status",
            "/api/desktop/prepare-shutdown",
        }:
            return await call_next(request)
        if not self.auth.is_authenticated(request):
            return JSONResponse(
                status_code=401,
                content={
                    "code": "desktop_session_required",
                    "message": "The private desktop session is not authenticated.",
                },
            )
        return await call_next(request)


class DesktopShutdownGate:
    """Atomically reject new writes once desktop shutdown is committed."""

    def __init__(self) -> None:
        self._guard = threading.Lock()
        self._writes_in_flight = 0
        self._committed = False

    def begin_write(self) -> bool:
        with self._guard:
            if self._committed:
                return False
            self._writes_in_flight += 1
            return True

    def end_write(self) -> None:
        with self._guard:
            self._writes_in_flight = max(0, self._writes_in_flight - 1)

    def commit_if_idle(self, has_active_work: Callable[[], bool]) -> bool:
        with self._guard:
            if self._writes_in_flight or has_active_work():
                return False
            self._committed = True
            return True


class DesktopShutdownMiddleware(BaseHTTPMiddleware):
    """Track mutating API work against the desktop shutdown gate."""

    def __init__(self, app: object, gate: DesktopShutdownGate) -> None:
        super().__init__(app)  # type: ignore[arg-type]
        self.gate = gate

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        is_write = request.method in {"POST", "PUT", "PATCH", "DELETE"}
        is_control = request.url.path == "/api/desktop/prepare-shutdown"
        if not is_write or is_control:
            return await call_next(request)
        if not self.gate.begin_write():
            return JSONResponse(
                status_code=409,
                content={
                    "code": "desktop_shutdown_committed",
                    "message": "Agent Kronig is closing and cannot start new work.",
                },
            )
        try:
            return await call_next(request)
        finally:
            self.gate.end_write()
