"""Narrow configuration boundary for the future licensed Sentaurus runner."""

from pathlib import Path

from pydantic import AnyHttpUrl

from tcad_agent.domain.models import StrictModel
from tcad_agent.runners.models import CompiledJob, NativeRunResult, RunBudget


class BackendUnconfiguredError(RuntimeError):
    pass


class RemoteRunnerConfig(StrictModel):
    endpoint: AnyHttpUrl | None = None
    trusted_public_key: str | None = None
    sentaurus_version: str | None = None

    @property
    def configured(self) -> bool:
        return bool(self.endpoint and self.trusted_public_key and self.sentaurus_version)


class RemoteSentaurusRunner:
    def __init__(self, config: RemoteRunnerConfig) -> None:
        self.config = config

    def run(self, job: CompiledJob, budget: RunBudget) -> NativeRunResult:
        if not self.config.configured:
            raise BackendUnconfiguredError(
                "Sentaurus runner requires endpoint, trusted key, and exact simulator version"
            )
        if job.backend != "sentaurus":
            raise ValueError("remote Sentaurus runner accepts only sentaurus jobs")
        raise BackendUnconfiguredError(
            "Remote transport is intentionally unavailable until the licensed machine is connected"
        )

    @staticmethod
    def verify_workspace(job: CompiledJob, workspace: Path) -> None:
        root = workspace.resolve()
        if any(not path.resolve().is_relative_to(root) for path in job.input_files):
            raise ValueError("remote job contains an artifact outside its workspace")
