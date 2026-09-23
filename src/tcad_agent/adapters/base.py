"""Stable adapter protocol shared by local and licensed backends."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Protocol

from tcad_agent.capabilities.models import CapabilityManifest
from tcad_agent.domain.models import ExperimentSpec

if TYPE_CHECKING:
    from tcad_agent.results.models import CanonicalResult
    from tcad_agent.runners.models import CompiledJob, NativeRunResult


class Adapter(Protocol):
    @property
    def manifest(self) -> CapabilityManifest: ...

    def compile(self, spec: ExperimentSpec, workspace: Path) -> CompiledJob: ...

    def normalize(self, native: NativeRunResult) -> CanonicalResult: ...

