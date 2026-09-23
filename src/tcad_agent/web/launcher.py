"""Loopback-only launcher used by the CLI and macOS command file."""

from __future__ import annotations

import json
import socket
import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from tcad_agent.web.app import create_app
from tcad_agent.web.runtime import runtime_fingerprint

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _health_fingerprint(url: str) -> str | None:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=0.5) as response:
            if response.status != 200:
                return None
            payload = json.loads(response.read())
            if payload.get("status") != "ok":
                return None
            value = payload.get("runtime_fingerprint")
            return value if isinstance(value, str) else None
    except (OSError, urllib.error.URLError, ValueError):
        return None


def _healthy(url: str, expected_fingerprint: str) -> bool:
    return _health_fingerprint(url) == expected_fingerprint


def _port_available(port: int) -> bool:
    with socket.socket() as probe:
        try:
            probe.bind((DEFAULT_HOST, port))
        except OSError:
            return False
    return True


def _select_port(default_port: int, expected_fingerprint: str) -> tuple[int, bool]:
    default_url = f"http://{DEFAULT_HOST}:{default_port}"
    if _healthy(default_url, expected_fingerprint):
        return default_port, True
    if _port_available(default_port):
        return default_port, False
    for port in range(default_port + 1, default_port + 101):
        if _port_available(port):
            return port, False
    raise RuntimeError("no local port is available for the TCAD Agent web application")


def _open_when_ready(url: str, expected_fingerprint: str) -> None:
    for _ in range(100):
        if _healthy(url, expected_fingerprint):
            webbrowser.open(url)
            return
        time.sleep(0.05)


def main() -> None:
    fingerprint = runtime_fingerprint()
    port, reused = _select_port(DEFAULT_PORT, fingerprint)
    url = f"http://{DEFAULT_HOST}:{port}"
    if reused:
        webbrowser.open(url)
        return
    threading.Thread(
        target=_open_when_ready,
        args=(url, fingerprint),
        daemon=True,
    ).start()
    uvicorn.run(
        create_app(runtime_id=fingerprint),
        host=DEFAULT_HOST,
        port=port,
        log_level="info",
    )
