"""Bounded, shell-free execution of one configured Sentaurus executable."""

from __future__ import annotations

import importlib
import math
import os
import signal
import subprocess
import time
from pathlib import Path
from typing import Literal, Protocol, cast

from tcad_agent.domain.models import StrictModel


class _ResourceModule(Protocol):
    RLIMIT_CPU: int
    RLIMIT_AS: int

    def setrlimit(self, resource: int, limits: tuple[int, int]) -> None: ...


resource_module = (
    cast(_ResourceModule, importlib.import_module("resource"))
    if os.name == "posix"
    else None
)


class ExecutorResult(StrictModel):
    status: Literal["completed", "execution_failed", "timed_out"]
    return_code: int | None
    elapsed_seconds: float
    error: str | None


class SentaurusExecutor:
    def __init__(self, executable: Path, *, memory_bytes: int = 4 * 1024**3) -> None:
        self.executable = executable.resolve()
        self.memory_bytes = memory_bytes

    def execute(self, job_dir: Path, *, timeout_seconds: float) -> ExecutorResult:
        if not self.executable.is_file() or not os.access(self.executable, os.X_OK):
            raise RuntimeError("the configured Sentaurus executable is unavailable")
        if resource_module is None:
            raise RuntimeError("Sentaurus execution requires a POSIX execution host")
        command_file = (job_dir / "sdevice.cmd").resolve()
        if not command_file.is_file() or not command_file.is_relative_to(job_dir.resolve()):
            raise ValueError("the allowlisted command file is unavailable")

        stdout_path = job_dir / "runner.stdout.log"
        stderr_path = job_dir / "runner.stderr.log"
        started = time.monotonic()

        def apply_limits() -> None:
            cpu_seconds = max(1, math.ceil(timeout_seconds))
            resource_module.setrlimit(
                resource_module.RLIMIT_CPU,
                (cpu_seconds, cpu_seconds + 1),
            )
            resource_module.setrlimit(
                resource_module.RLIMIT_AS,
                (self.memory_bytes, self.memory_bytes),
            )

        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                [str(self.executable), command_file.name],
                cwd=job_dir,
                env={"LANG": "C", "LC_ALL": "C"},
                stdin=subprocess.DEVNULL,
                stdout=stdout,
                stderr=stderr,
                shell=False,
                start_new_session=True,
                preexec_fn=apply_limits,
            )
            try:
                return_code = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait(timeout=5)
                return ExecutorResult(
                    status="timed_out",
                    return_code=process.returncode,
                    elapsed_seconds=time.monotonic() - started,
                    error="Sentaurus execution exceeded the configured wall-time limit",
                )
        if return_code != 0:
            return ExecutorResult(
                status="execution_failed",
                return_code=return_code,
                elapsed_seconds=time.monotonic() - started,
                error="Sentaurus returned a nonzero exit status",
            )
        return ExecutorResult(
            status="completed",
            return_code=return_code,
            elapsed_seconds=time.monotonic() - started,
            error=None,
        )
