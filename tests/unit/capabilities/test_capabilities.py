from tcad_agent.capabilities.models import CapabilityManifest, CapabilityStatus
from tcad_agent.capabilities.service import CapabilityService
from tcad_agent.domain.models import DCStudy, ExperimentSpec, Region1D


def test_refuses_model_missing_from_backend(valid_spec: ExperimentSpec) -> None:
    requested = valid_spec.model_copy(
        update={"physics": valid_spec.physics.model_copy(update={"models": ("hydrodynamic",)})}
    )
    manifest = CapabilityManifest.model_validate(
        {
            "backend": "devsim",
            "dimensions": [1],
            "equations": ["poisson"],
            "models": [],
        }
    )
    decision = CapabilityService().check(requested, manifest)
    assert decision.status is CapabilityStatus.BACKEND_UNSUPPORTED
    assert decision.issues[0].path == "physics.equations[1]"
    assert "physics.models[0]" in {issue.path for issue in decision.issues}


def test_same_composition_can_target_two_manifests(
    valid_spec: ExperimentSpec,
    devsim_manifest: CapabilityManifest,
    sentaurus_manifest: CapabilityManifest,
) -> None:
    service = CapabilityService()
    assert service.check(valid_spec, devsim_manifest).status is CapabilityStatus.SUPPORTED
    assert service.check(valid_spec, sentaurus_manifest).status is CapabilityStatus.SUPPORTED


def test_backend_manifest_reports_execution_configuration(
    sentaurus_manifest: CapabilityManifest,
) -> None:
    assert sentaurus_manifest.execution_state == "unconfigured"


def test_backend_limits_reject_oversized_sweep(
    valid_spec: ExperimentSpec, devsim_manifest: CapabilityManifest
) -> None:
    study = DCStudy.model_validate(
        {"kind": "dc", "contact": "anode", "start": "0 V", "stop": "1 V", "step": "0.1 V"}
    )
    requested = valid_spec.model_copy(update={"study": study})

    decision = CapabilityService().check(requested, devsim_manifest)

    assert decision.status is CapabilityStatus.BACKEND_UNSUPPORTED
    assert "study.bias_points" in {issue.path for issue in decision.issues}


def test_backend_limits_reject_too_many_regions(
    valid_spec: ExperimentSpec, devsim_manifest: CapabilityManifest
) -> None:
    regions = tuple(
        Region1D.model_validate(
            {
                "id": f"r{index}",
                "material": "silicon",
                "x0": f"{index} nm",
                "x1": f"{index + 1} nm",
            }
        )
        for index in range(33)
    )
    requested = valid_spec.model_copy(update={"regions": regions, "profiles": ()})

    decision = CapabilityService().check(requested, devsim_manifest)

    assert decision.status is CapabilityStatus.BACKEND_UNSUPPORTED
    assert "regions" in {issue.path for issue in decision.issues}
