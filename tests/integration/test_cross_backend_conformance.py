import os
from pathlib import Path

import pytest

from tcad_agent.adapters.sentaurus.normalizer import SentaurusNormalizer
from tcad_agent.conformance.compare import compare_results
from tcad_agent.conformance.models import ComparisonRule, ComparisonStatus
from tcad_agent.runners.models import NativeRunResult


def test_fixture_based_cross_backend_comparison() -> None:
    path = Path("tests/fixtures/sentaurus/results/equilibrium_1d.json")
    sentaurus = SentaurusNormalizer().normalize(
        NativeRunResult(
            backend="sentaurus",
            status="completed",
            return_code=0,
            stdout_path=path.parent / "stdout.log",
            stderr_path=path.parent / "stderr.log",
            result_path=path,
            elapsed_seconds=1.0,
        )
    )
    devsim_like = sentaurus.model_copy(update={"backend": "devsim"})
    report = compare_results(
        devsim_like,
        sentaurus,
        (
            ComparisonRule(
                metric="built_in_potential",
                field="potential",
                relative_tolerance=0.05,
                absolute_tolerance=1.0e-3,
            ),
        ),
    )
    assert report.overall is ComparisonStatus.PASSED


@pytest.mark.sentaurus
def test_live_licensed_cross_backend_conformance() -> None:
    required = (
        "TCAD_SENTAURUS_ENDPOINT",
        "TCAD_SENTAURUS_SIGNING_PRIVATE_KEY",
        "TCAD_SENTAURUS_TRUSTED_PUBLIC_KEY",
        "TCAD_SENTAURUS_VERSION",
    )
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        pytest.skip("licensed Sentaurus runner is not configured: " + ", ".join(missing))
    pytest.fail("live fixture submission is reserved for the reviewed licensed-machine run")

