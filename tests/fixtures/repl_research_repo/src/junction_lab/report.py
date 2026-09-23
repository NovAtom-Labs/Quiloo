"""Deterministic Markdown reporting."""

from __future__ import annotations


def render_report(
    summary: dict[str, float | str],
    *,
    input_sha256: str,
) -> str:
    del input_sha256
    return "\n".join(
        (
            f"# {summary['experiment']}",
            "",
            "## Equilibrium summary",
            "",
            f"- Built-in potential: {summary['built_in_potential_v']:.6g} V",
            f"- Depletion width: {summary['depletion_width_m']:.6g} m",
            (
                "- Peak electric field: "
                f"{summary['peak_electric_field_v_per_m']:.6g} V/m"
            ),
            "- Equilibrium current density: 0 A/m^2",
            "",
            f"Model: {summary['model_version']}",
            "",
        )
    )
