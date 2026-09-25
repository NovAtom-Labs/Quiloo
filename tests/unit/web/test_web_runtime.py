import socket
from pathlib import Path

import pytest

from tcad_agent.desktop.lock import DataDirectoryLock, DesktopDataLockError
from tcad_agent.web import launcher
from tcad_agent.web.launcher import DEFAULT_HOST, _select_port
from tcad_agent.web.runtime import runtime_fingerprint


def test_runtime_fingerprint_excludes_bedrock_secret(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "bedrock/global.anthropic.claude-sonnet-4-6")
    monkeypatch.setenv("AWS_REGION_NAME", "ap-south-1")
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "first-secret")
    first = runtime_fingerprint()
    monkeypatch.setenv("AWS_BEARER_TOKEN_BEDROCK", "second-secret")
    assert runtime_fingerprint() == first


def test_runtime_fingerprint_changes_with_model(monkeypatch) -> None:
    monkeypatch.setenv("LLM_MODEL", "bedrock/model-a")
    first = runtime_fingerprint()
    monkeypatch.setenv("LLM_MODEL", "bedrock/model-b")
    assert runtime_fingerprint() != first


def test_select_port_uses_next_free_port_when_default_is_occupied() -> None:
    with socket.socket() as occupied:
        occupied.bind(("127.0.0.1", 0))
        port = occupied.getsockname()[1]
        selected, reused = _select_port(
            DEFAULT_HOST, port, expected_fingerprint="new-runtime"
        )
    assert selected != port
    assert reused is False


def test_run_server_can_launch_without_opening_browser(monkeypatch) -> None:
    calls: dict[str, object] = {}
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])

    def fake_run(app, *, host, port, log_level) -> None:
        calls.update(app=app, host=host, port=port, log_level=log_level)

    monkeypatch.setattr(launcher.uvicorn, "run", fake_run)
    monkeypatch.setattr(
        launcher.webbrowser,
        "open",
        lambda _url: calls.update(browser_opened=True),
    )

    launcher.run_server("127.0.0.1", port, open_browser=False)

    assert calls["host"] == "127.0.0.1"
    assert calls["port"] == port
    assert "browser_opened" not in calls


def test_browser_server_refuses_a_data_directory_owned_by_desktop(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime = tmp_path / "runtime"
    monkeypatch.setenv("TCAD_WORKSPACE", str(runtime))
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        port = int(probe.getsockname()[1])
    with DataDirectoryLock(runtime):
        with pytest.raises(DesktopDataLockError):
            launcher.run_server("127.0.0.1", port, open_browser=False)
