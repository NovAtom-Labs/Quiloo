from pathlib import Path

import pytest

from tcad_agent.evaluations.agent_cases import AgentEvaluationSuite

ROOT = Path(__file__).parents[3]
SUITE_PATH = ROOT / "evaluations" / "agent" / "cases.yaml"


def test_equilibrium_metal_silicon_case_preserves_request_and_requires_clarification() -> None:
    suite = AgentEvaluationSuite.from_file(SUITE_PATH)

    case = suite.require_case("metal-silicon-junction-equilibrium")

    assert case.requested_backend == "sentaurus"
    assert case.expected_stage == "clarification_required"
    assert case.required_clarifications == (
        "region_thicknesses",
        "metal_semiconductor_contact_treatment",
    )
    assert case.preserved_facts == (
        "temperature_300_K",
        "acceptor_concentration_1e17_cm-3",
        "donor_concentration_1e17_cm-3",
        "aluminum_work_function_4.10_eV",
        "left_contact_0_V",
        "right_contact_0_V",
        "no_voltage_sweep",
    )
    assert set(case.required_physics) == {
        "fermi",
        "mobility",
        "srh",
        "auger",
        "band_gap_narrowing",
    }
    assert "zero_electron_current_density" in case.equilibrium_invariants
    assert "zero_hole_current_density" in case.equilibrium_invariants
    assert "constant_fermi_level" in case.equilibrium_invariants
    assert "silent_backend_substitution" in case.prohibited_behaviors
    assert "invented_geometry" in case.prohibited_behaviors


def test_agent_case_prompt_is_loaded_from_the_user_copyable_example() -> None:
    suite = AgentEvaluationSuite.from_file(SUITE_PATH)

    prompt = suite.read_prompt("metal-silicon-junction-equilibrium")

    assert prompt.startswith("# Equilibrium Al / p-Si / n-Si / Al")
    assert "both contacts maintained at 0 V" in prompt
    assert "Band-gap narrowing" in prompt


def test_agent_suite_rejects_unknown_case_ids() -> None:
    suite = AgentEvaluationSuite.from_file(SUITE_PATH)

    with pytest.raises(KeyError, match="unknown agent evaluation case"):
        suite.require_case("not-a-real-case")
