"""Managed loopback backend entrypoint for the Electron desktop shell."""

from __future__ import annotations

import json
import os
import socket
import sys
from collections.abc import Mapping
from typing import TextIO

import uvicorn
from fastapi import FastAPI

from tcad_agent.desktop.auth import DesktopAuth
from tcad_agent.desktop.config import DesktopLaunchConfig
from tcad_agent.desktop.lock import DataDirectoryLock, DesktopDataLockError
from tcad_agent.web.app import create_app
from tcad_agent.web.ide_routes import build_default_ide_services
from tcad_agent.web.runtime import runtime_fingerprint


def readiness_record(
    config: DesktopLaunchConfig,
    *,
    url: str,
    pid: int,
    fingerprint: str,
) -> dict[str, str | int]:
    """Return the versioned machine-readable shell handshake."""

    return {
        "protocol": config.protocol_version,
        "url": url,
        "pid": pid,
        "runtime_fingerprint": fingerprint,
    }


def bind_desktop_socket(config: DesktopLaunchConfig) -> socket.socket:
    """Bind and listen before advertising desktop readiness."""

    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((config.host, config.port))
        listener.listen(128)
        return listener
    except Exception:
        listener.close()
        raise


def create_desktop_app(config: DesktopLaunchConfig) -> FastAPI:
    """Create one authenticated application rooted in the desktop data path."""

    os.environ["TCAD_WORKSPACE"] = str(config.data_dir)
    if config.devsim_runner is not None:
        os.environ["AGENT_KRONIG_DEVSIM_RUNNER"] = str(config.devsim_runner)
    services = build_default_ide_services()
    return create_app(
        runtime_id=runtime_fingerprint(),
        ide=services,
        desktop_auth=DesktopAuth(config.launch_token),
    )


def serve_desktop(
    config: DesktopLaunchConfig,
    *,
    output: TextIO = sys.stdout,
) -> None:
    """Run the authenticated desktop backend until the owning shell exits."""

    config.data_dir.mkdir(parents=True, exist_ok=True)
    with DataDirectoryLock(config.data_dir):
        listener = bind_desktop_socket(config)
        try:
            host, port = listener.getsockname()
            fingerprint = runtime_fingerprint()
            record = readiness_record(
                config,
                url=f"http://{host}:{port}",
                pid=os.getpid(),
                fingerprint=fingerprint,
            )
            output.write(json.dumps(record, separators=(",", ":")) + "\n")
            output.flush()
            server = uvicorn.Server(
                uvicorn.Config(
                    create_desktop_app(config),
                    log_level="info",
                    access_log=False,
                )
            )
            server.run(sockets=[listener])
        finally:
            listener.close()


def main(environment: Mapping[str, str] | None = None) -> None:
    """Console entrypoint used by Electron and packaged sidecars."""

    try:
        serve_desktop(DesktopLaunchConfig.from_environment(environment))
    except (ValueError, DesktopDataLockError, OSError) as exc:
        print(f"Agent Kronig desktop backend could not start: {exc}", file=sys.stderr)
        raise SystemExit(2) from exc


if __name__ == "__main__":
    main()
