"""Single composition point for backend-specific adapters and runners."""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from tcad_agent.adapters.base import Adapter
from tcad_agent.adapters.devsim.compiler import DevsimAdapter
from tcad_agent.adapters.sentaurus.compiler import SentaurusAdapter
from tcad_agent.runners.local import LocalRunner
from tcad_agent.runners.models import CompiledJob, NativeRunResult, RunBudget
from tcad_agent.runners.remote import RemoteRunnerConfig, RemoteSentaurusRunner


class BackendAdapterUnavailable(RuntimeError):
    """Raised when a declared backend has no installed execution binding."""


class Runner(Protocol):
    def run(self, job: CompiledJob, budget: RunBudget) -> NativeRunResult: ...


@dataclass(frozen=True)
class BackendBinding:
    adapter: Adapter
    runner: Runner


def get_backend(backend: str) -> BackendBinding:
    """Return the installed backend binding or refuse at one explicit seam."""
    if backend == "devsim":
        devsim_python = Path(
            os.getenv("TCAD_DEVSIM_PYTHON")
            or str(Path.cwd().parent / "devsim" / ".venv" / "bin" / "python")
        )
        return BackendBinding(
            adapter=DevsimAdapter.from_defaults(),
            runner=LocalRunner(devsim_python),
        )
    if backend == "sentaurus":
        return BackendBinding(
            adapter=SentaurusAdapter.from_defaults(),
            runner=RemoteSentaurusRunner(RemoteRunnerConfig.from_environment()),
        )
    raise BackendAdapterUnavailable(f"{backend} adapter and runner are not installed")
