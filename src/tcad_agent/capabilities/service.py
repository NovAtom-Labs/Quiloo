"""Data-driven comparison of experiment requests and backend support."""

from tcad_agent.capabilities.models import (
    CapabilityDecision,
    CapabilityIssue,
    CapabilityManifest,
    CapabilityStatus,
)
from tcad_agent.domain.models import ExperimentSpec


class CapabilityService:
    """Checks requested features without interpreting device names."""

    def check(
        self, spec: ExperimentSpec, manifest: CapabilityManifest
    ) -> CapabilityDecision:
        issues: list[CapabilityIssue] = []
        self._check_one(issues, "dimension", spec.dimension, manifest.dimensions)
        self._check_many(
            issues,
            "physics.equations",
            tuple(str(value) for value in spec.physics.equations),
            manifest.equations,
        )
        self._check_many(issues, "physics.models", spec.physics.models, manifest.models)
        self._check_many(
            issues,
            "profiles",
            tuple(profile.kind for profile in spec.profiles),
            manifest.profiles,
        )
        self._check_many(
            issues,
            "contacts",
            tuple(str(contact.kind) for contact in spec.contacts),
            manifest.contacts,
        )
        self._check_one(issues, "study.kind", spec.study.kind, manifest.studies)
        self._check_many(
            issues,
            "observables",
            tuple(str(observable) for observable in spec.observables),
            manifest.observables,
        )
        status = (
            CapabilityStatus.BACKEND_UNSUPPORTED if issues else CapabilityStatus.SUPPORTED
        )
        return CapabilityDecision(status=status, backend=manifest.backend, issues=tuple(issues))

    @staticmethod
    def _check_one(
        issues: list[CapabilityIssue],
        path: str,
        requested: str | int,
        supported: tuple[str | int, ...],
    ) -> None:
        if requested not in supported:
            issues.append(
                CapabilityIssue(
                    path=path,
                    code="unsupported_capability",
                    message=f"{requested!r} is not supported by this backend",
                    requested=requested,
                    supported=supported,
                )
            )

    @classmethod
    def _check_many(
        cls,
        issues: list[CapabilityIssue],
        path: str,
        requested: tuple[str, ...],
        supported: tuple[str, ...],
    ) -> None:
        for index, value in enumerate(requested):
            cls._check_one(issues, f"{path}[{index}]", value, supported)

