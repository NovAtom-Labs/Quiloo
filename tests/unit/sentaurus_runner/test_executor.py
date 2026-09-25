from pathlib import Path

import pytest

from tcad_agent.sentaurus_runner import executor
from tcad_agent.sentaurus_runner.executor import SentaurusExecutor


def test_execution_refuses_a_host_without_posix_resource_limits(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    executable = tmp_path / "sdevice"
    executable.write_text("licensed simulator placeholder")
    executable.chmod(0o700)
    job = tmp_path / "job"
    job.mkdir()
    (job / "sdevice.cmd").write_text("Solve {}\n")
    monkeypatch.setattr(executor, "resource_module", None)

    with pytest.raises(RuntimeError, match="POSIX execution host"):
        SentaurusExecutor(executable).execute(job, timeout_seconds=30)
