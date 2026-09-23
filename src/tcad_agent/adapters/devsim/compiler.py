"""Deterministic compiler and normalizer for the DEVSIM backend."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

from tcad_agent.adapters.devsim import runtime
from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.domain.errors import CapabilityError
from tcad_agent.domain.models import DCStudy, ExperimentSpec, ProfileSpecies
from tcad_agent.results.models import BiasPoint, CanonicalResult, FieldSeries
from tcad_agent.runners.models import CompiledJob, NativeRunResult


class DevsimAdapter:
    compiler_version = "0.1.0"

    def __init__(self, manifest: CapabilityManifest) -> None:
        self._manifest = manifest

    @property
    def manifest(self) -> CapabilityManifest:
        return self._manifest

    @classmethod
    def from_defaults(cls) -> DevsimAdapter:
        return cls(CapabilityManifest.from_backend("devsim"))

    def compile(self, spec: ExperimentSpec, workspace: Path) -> CompiledJob:
        decision = CapabilityService().check(spec, self.manifest)
        if decision.status is not CapabilityStatus.SUPPORTED:
            details = "; ".join(f"{issue.path}: {issue.message}" for issue in decision.issues)
            raise CapabilityError(details)
        payload = self._payload(spec)
        workspace = workspace.resolve()
        input_bytes = (json.dumps(payload, sort_keys=True, indent=2) + "\n").encode()
        runtime_path = Path(runtime.__file__)
        runtime_bytes = runtime_path.read_bytes()
        workspace.mkdir(parents=True, exist_ok=False)
        input_path = workspace / "input.json"
        entrypoint = workspace / "run_devsim.py"
        input_path.write_bytes(input_bytes)
        entrypoint.write_bytes(runtime_bytes)
        return CompiledJob(
            backend="devsim",
            entrypoint=entrypoint,
            arguments=(str(input_path.name),),
            environment={},
            input_files=(input_path, entrypoint),
            input_digest=hashlib.sha256(input_bytes).hexdigest(),
            runtime_digest=hashlib.sha256(runtime_bytes).hexdigest(),
            compiler_version=self.compiler_version,
        )

    def _payload(self, spec: ExperimentSpec) -> dict[str, object]:
        doping = {region.id: 0.0 for region in spec.regions}
        for profile in spec.profiles:
            sign = 1.0 if profile.species is ProfileSpecies.DONOR else -1.0
            doping[profile.region] += sign * profile.value.to("cm^-3")
        mesh_lines: list[dict[str, float | str]] = []
        for index, region in enumerate(spec.regions):
            spacing = (
                region.mesh_spacing.to("cm")
                if region.mesh_spacing is not None
                else max((region.x1.to("cm") - region.x0.to("cm")) / 50.0, 1e-9)
            )
            if index == 0:
                mesh_lines.append(
                    {"position_cm": region.x0.to("cm"), "spacing_cm": spacing, "tag": "x_min"}
                )
            tag = "x_max" if index == len(spec.regions) - 1 else f"boundary_{index}"
            mesh_lines.append(
                {"position_cm": region.x1.to("cm"), "spacing_cm": spacing, "tag": tag}
            )
        contacts = {str(contact.location): contact.id for contact in spec.contacts}
        study: dict[str, object] = {"kind": spec.study.kind}
        if isinstance(spec.study, DCStudy):
            start = Decimal(str(spec.study.start.to("V")))
            stop = Decimal(str(spec.study.stop.to("V")))
            step = Decimal(str(spec.study.step.to("V")))
            values: list[float] = []
            current = start
            while current <= stop:
                values.append(float(current))
                current += step
            study.update({"contact": spec.study.contact, "biases_v": values})
        return {
            "schema_version": "1.0",
            "experiment_name": spec.name,
            "mesh_lines": mesh_lines,
            "segments": [
                {"x1_cm": region.x1.to("cm"), "net_doping_cm3": doping[region.id]}
                for region in spec.regions
            ],
            "contacts": contacts,
            "temperature_k": spec.physics.temperature.to("K"),
            "study": study,
            "observables": [str(value) for value in spec.observables],
        }

    def normalize(self, native: NativeRunResult) -> CanonicalResult:
        if native.status != "completed" or native.result_path is None:
            return CanonicalResult(
                backend="devsim",
                status=native.status,
                native_result_path=native.result_path,
                error=native.error,
            )
        data = json.loads(native.result_path.read_text())
        points = tuple(
            BiasPoint(
                bias_v=point["bias_v"],
                converged=point["converged"],
                terminal_currents_a_per_m2={
                    name: value * 1e4 for name, value in point["currents_a_per_cm2"].items()
                },
            )
            for point in data["bias_points"]
        )
        fields: dict[str, FieldSeries] = {}
        for name, field in data["fields"].items():
            scale = {"cm^-3": 1e6, "V/cm": 1e2}.get(field["unit"], 1.0)
            unit = {"cm^-3": "m^-3", "V/cm": "V/m"}.get(
                field["unit"], field["unit"]
            )
            fields[name] = FieldSeries(
                positions_m=tuple(value * 1e-2 for value in field["positions_cm"]),
                values=tuple(value * scale for value in field["values"]),
                unit=unit,
            )
        return CanonicalResult(
            backend="devsim",
            simulator_version=data["simulator_version"],
            status="completed",
            terminals=tuple(data["terminals"]),
            bias_points=points,
            fields=fields,
            native_result_path=native.result_path,
        )
