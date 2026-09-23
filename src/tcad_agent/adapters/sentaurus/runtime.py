"""Typed metadata emitted for the licensed Sentaurus runner."""

from typing import Literal

from pydantic import Field

from tcad_agent.domain.models import StrictModel


class SourceLocation(StrictModel):
    file: str
    line: int = Field(ge=1)


class SentaurusJobManifest(StrictModel):
    schema_version: Literal["1.0"] = "1.0"
    backend: Literal["sentaurus"] = "sentaurus"
    compiler_version: str
    command_file: Literal["sdevice.cmd"] = "sdevice.cmd"
    required_runtime_inputs: tuple[Literal["device.tdr"], ...] = ("device.tdr",)
    expected_outputs: tuple[str, ...]
    inputs: dict[str, str]
    source_map: dict[str, SourceLocation]

