"""Signed HTTP client for the licensed Sentaurus runner."""

from __future__ import annotations

import base64
import binascii
import hashlib
import io
import zipfile
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import UUID, uuid4

import httpx
from pydantic import AnyHttpUrl, field_validator

from tcad_agent.domain.models import StrictModel
from tcad_agent.remote_protocol.models import (
    RemoteJobHandle,
    RemoteJobResult,
    RemoteJobState,
    RemoteJobStatus,
    SubmitJobPayload,
)
from tcad_agent.remote_protocol.signing import sign_submit_request
from tcad_agent.runners.models import CompiledJob, NativeRunResult, RunBudget


class BackendUnconfiguredError(RuntimeError):
    pass


class RemoteProtocolError(RuntimeError):
    pass


class RemoteRunnerConfig(StrictModel):
    endpoint: AnyHttpUrl | None = None
    signing_private_key: str | None = None
    trusted_public_key: str | None = None
    sentaurus_version: str | None = None
    timeout_seconds: float = 30

    @field_validator("endpoint")
    @classmethod
    def require_secure_endpoint(cls, value: AnyHttpUrl | None) -> AnyHttpUrl | None:
        if value is None:
            return value
        host = value.host or ""
        if value.scheme != "https" and host not in {"127.0.0.1", "localhost", "testserver"}:
            raise ValueError("remote runner endpoint must use HTTPS")
        return value

    @property
    def configured(self) -> bool:
        return bool(
            self.endpoint
            and self.signing_private_key
            and self.trusted_public_key
            and self.sentaurus_version
        )


class RemoteSentaurusRunner:
    def __init__(
        self,
        config: RemoteRunnerConfig,
        *,
        client: httpx.Client | None = None,
        clock: Callable[[], datetime] | None = None,
        uuid_factory: Callable[[], UUID] | None = None,
    ) -> None:
        self.config = config
        self._client = client or httpx.Client(timeout=config.timeout_seconds)
        self._clock = clock or (lambda: datetime.now(UTC))
        self._uuid_factory = uuid_factory or uuid4
        self._workspaces: dict[UUID, Path] = {}

    def submit(self, job: CompiledJob, budget: RunBudget) -> RemoteJobHandle:
        del budget
        self._require_configured()
        if job.backend != "sentaurus":
            raise ValueError("remote Sentaurus runner accepts only sentaurus jobs")
        workspace = job.entrypoint.parent.resolve()
        self.verify_workspace(job, workspace)
        bundle = self._bundle(job, workspace)
        now = self._clock()
        job_id = self._uuid_factory()
        assert self.config.sentaurus_version is not None
        assert self.config.signing_private_key is not None
        payload = SubmitJobPayload(
            job_id=job_id,
            required_simulator_version=self.config.sentaurus_version,
            manifest_sha256=hashlib.sha256(bundle).hexdigest(),
            bundle_b64=base64.b64encode(bundle).decode(),
            issued_at=now,
            expires_at=now + timedelta(minutes=5),
        )
        request = sign_submit_request(payload, self.config.signing_private_key)
        response = self._client.post(self._url("/v1/jobs"), json=request.model_dump(mode="json"))
        self._require_success(response, expected=201)
        handle = RemoteJobHandle.model_validate(response.json())
        if handle.job_id != job_id:
            raise RemoteProtocolError("runner returned a different job ID")
        self._workspaces[job_id] = workspace
        return handle

    def status(self, handle: RemoteJobHandle) -> RemoteJobStatus:
        response = self._client.get(self._url(f"/v1/jobs/{handle.job_id}/status"))
        self._require_success(response)
        status = RemoteJobStatus.model_validate(response.json())
        if status.job_id != handle.job_id:
            raise RemoteProtocolError("runner returned a different job ID")
        return status

    def result(self, handle: RemoteJobHandle) -> NativeRunResult:
        response = self._client.get(self._url(f"/v1/jobs/{handle.job_id}/result"))
        self._require_success(response)
        remote = RemoteJobResult.model_validate(response.json())
        if remote.job_id != handle.job_id:
            raise RemoteProtocolError("runner returned a different job ID")
        workspace = self._workspaces.get(handle.job_id)
        if workspace is None:
            raise RemoteProtocolError("job workspace is unavailable")
        output = workspace / "remote-result"
        output.mkdir(mode=0o700, exist_ok=True)
        paths: dict[str, Path] = {}
        for name, encoded in remote.files_b64.items():
            if Path(name).name != name or name not in remote.files_sha256:
                raise RemoteProtocolError("runner returned an unsafe output name")
            try:
                data = base64.b64decode(encoded, validate=True)
            except (ValueError, binascii.Error) as exc:
                raise RemoteProtocolError("runner returned invalid output data") from exc
            if hashlib.sha256(data).hexdigest() != remote.files_sha256[name]:
                raise RemoteProtocolError("runner output digest does not match")
            path = output / name
            path.write_bytes(data)
            paths[name] = path
        stdout = paths.get("runner.stdout.log", output / "runner.stdout.log")
        stderr = paths.get("runner.stderr.log", output / "runner.stderr.log")
        stdout.touch(exist_ok=True)
        stderr.touch(exist_ok=True)
        native_result = paths.get("sentaurus-result.json") or paths.get("sdevice.tdr")
        return NativeRunResult(
            backend="sentaurus",
            status=remote.status,
            return_code=remote.return_code,
            stdout_path=stdout,
            stderr_path=stderr,
            result_path=native_result,
            elapsed_seconds=remote.elapsed_seconds,
            error=remote.error,
        )

    def run(self, job: CompiledJob, budget: RunBudget) -> NativeRunResult:
        handle = self.submit(job, budget)
        status = self.status(handle)
        if status.state not in {
            RemoteJobState.COMPLETED,
            RemoteJobState.FAILED,
            RemoteJobState.TIMED_OUT,
        }:
            raise RemoteProtocolError("runner has not completed the synchronous request")
        return self.result(handle)

    def _require_configured(self) -> None:
        if not self.config.configured:
            raise BackendUnconfiguredError(
                "Sentaurus runner requires endpoint, signing key, trusted key, "
                "and exact simulator version"
            )

    def _url(self, path: str) -> str:
        assert self.config.endpoint is not None
        return str(self.config.endpoint).rstrip("/") + path

    @staticmethod
    def _require_success(response: httpx.Response, *, expected: int = 200) -> None:
        if response.status_code != expected:
            raise RemoteProtocolError(
                f"licensed runner request failed with status {response.status_code}"
            )

    @staticmethod
    def _bundle(job: CompiledJob, workspace: Path) -> bytes:
        stream = io.BytesIO()
        with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_STORED) as archive:
            for path in sorted(job.input_files, key=lambda item: item.name):
                relative = path.resolve().relative_to(workspace)
                if len(relative.parts) != 1:
                    raise ValueError("remote job inputs must be flat files")
                info = zipfile.ZipInfo(relative.as_posix(), (1980, 1, 1, 0, 0, 0))
                info.external_attr = 0o600 << 16
                archive.writestr(info, path.read_bytes())
        return stream.getvalue()

    @staticmethod
    def verify_workspace(job: CompiledJob, workspace: Path) -> None:
        root = workspace.resolve()
        if any(not path.resolve().is_relative_to(root) for path in job.input_files):
            raise ValueError("remote job contains an artifact outside its workspace")
