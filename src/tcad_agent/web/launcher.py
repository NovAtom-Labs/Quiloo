"""Loopback-only launcher used by the CLI and macOS command file."""

from __future__ import annotations

import threading
import time
import urllib.error
import urllib.request
import webbrowser

import uvicorn

from tcad_agent.web.app import create_app

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765


def _healthy(url: str) -> bool:
    try:
        with urllib.request.urlopen(f"{url}/health", timeout=0.5) as response:
            return bool(response.status == 200)
    except (OSError, urllib.error.URLError):
        return False


def _open_when_ready(url: str) -> None:
    for _ in range(100):
        if _healthy(url):
            webbrowser.open(url)
            return
        time.sleep(0.05)


def main() -> None:
    url = f"http://{DEFAULT_HOST}:{DEFAULT_PORT}"
    if _healthy(url):
        webbrowser.open(url)
        return
    threading.Thread(target=_open_when_ready, args=(url,), daemon=True).start()
    uvicorn.run(
        create_app(),
        host=DEFAULT_HOST,
        port=DEFAULT_PORT,
        log_level="info",
    )
