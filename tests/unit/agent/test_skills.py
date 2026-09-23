from pathlib import Path

from openhands.sdk.skills import load_skills_from_dir

ROOT = Path(__file__).parents[3]
SKILLS_ROOT = ROOT / "skills"


def test_all_skills_load_through_openhands() -> None:
    _, _, skills = load_skills_from_dir(SKILLS_ROOT)
    assert set(skills) == {
        "specification",
        "capability-checking",
        "devsim-compilation",
        "solver-recovery",
        "result-validation",
        "source-citation",
        "reporting",
        "sentaurus-boundary",
    }


def test_skill_descriptions_are_progressive_and_discriminating() -> None:
    _, _, skills = load_skills_from_dir(SKILLS_ROOT)
    for skill in skills.values():
        assert skill.description.startswith("Use when")
        assert len(skill.description) <= 500
