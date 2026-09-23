"""Reviewed DEVSIM runtime copied unchanged into compiled workspaces.

The implementation uses DEVSIM's Apache-2.0 `simple_physics` helpers and
follows the official one-dimensional diode example. It consumes only the
compiler-produced JSON payload and never accepts executable source text.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any


def _doping_expression(segments: list[dict[str, float]]) -> str:
    expression = f"{segments[-1]['net_doping_cm3']:.17g}"
    for segment in reversed(segments[:-1]):
        expression = (
            f"ifelse(x < {segment['x1_cm']:.17g}, "
            f"{segment['net_doping_cm3']:.17g}, {expression})"
        )
    return expression


def _bias_points(study: dict[str, Any]) -> list[float]:
    if study["kind"] == "equilibrium":
        return [0.0]
    return [float(value) for value in study["biases_v"]]


def main() -> int:
    import devsim  # type: ignore[import-not-found]
    from devsim import (
        add_1d_contact,
        add_1d_mesh_line,
        add_1d_region,
        create_1d_mesh,
        create_device,
        finalize_mesh,
        get_contact_current,
        get_node_model_values,
        set_node_values,
        set_parameter,
        solve,
    )
    from devsim.python_packages.model_create import (  # type: ignore[import-not-found]
        CreateNodeModel,
        CreateSolution,
    )
    from devsim.python_packages.simple_physics import (  # type: ignore[import-not-found]
        CreateSiliconDriftDiffusion,
        CreateSiliconDriftDiffusionAtContact,
        CreateSiliconPotentialOnly,
        CreateSiliconPotentialOnlyContact,
        GetContactBiasName,
        SetSiliconParameters,
    )

    payload_path = Path(sys.argv[1] if len(sys.argv) > 1 else "input.json")
    payload = json.loads(payload_path.read_text())
    device = "novatom_device"
    region = "bulk"
    mesh = "novatom_mesh"

    create_1d_mesh(mesh=mesh)
    for line in payload["mesh_lines"]:
        add_1d_mesh_line(
            mesh=mesh,
            pos=line["position_cm"],
            ps=line["spacing_cm"],
            tag=line["tag"],
        )
    add_1d_contact(
        mesh=mesh,
        name=payload["contacts"]["x_min"],
        tag="x_min",
        material="metal",
    )
    add_1d_contact(
        mesh=mesh,
        name=payload["contacts"]["x_max"],
        tag="x_max",
        material="metal",
    )
    add_1d_region(mesh=mesh, material="Si", region=region, tag1="x_min", tag2="x_max")
    finalize_mesh(mesh=mesh)
    create_device(mesh=mesh, device=device)

    SetSiliconParameters(device, region, payload["temperature_k"])
    set_parameter(device=device, region=region, name="taun", value=1e-8)
    set_parameter(device=device, region=region, name="taup", value=1e-8)
    CreateNodeModel(device, region, "NetDoping", _doping_expression(payload["segments"]))

    CreateSolution(device, region, "Potential")
    CreateSiliconPotentialOnly(device, region)
    for contact in payload["contacts"].values():
        set_parameter(device=device, name=GetContactBiasName(contact), value=0.0)
        CreateSiliconPotentialOnlyContact(device, region, contact)
    solve(type="dc", absolute_error=1.0, relative_error=1e-10, maximum_iterations=50)

    CreateSolution(device, region, "Electrons")
    CreateSolution(device, region, "Holes")
    set_node_values(device=device, region=region, name="Electrons", init_from="IntrinsicElectrons")
    set_node_values(device=device, region=region, name="Holes", init_from="IntrinsicHoles")
    CreateSiliconDriftDiffusion(device, region)
    for contact in payload["contacts"].values():
        CreateSiliconDriftDiffusionAtContact(device, region, contact)
    solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=50)

    requested_contact = payload["study"].get("contact")
    points: list[dict[str, Any]] = []
    for bias in _bias_points(payload["study"]):
        if requested_contact is not None:
            set_parameter(
                device=device,
                name=GetContactBiasName(requested_contact),
                value=bias,
            )
            solve(type="dc", absolute_error=1e10, relative_error=1e-10, maximum_iterations=50)
        currents: dict[str, float] = {}
        for contact in payload["contacts"].values():
            electron = get_contact_current(
                device=device,
                contact=contact,
                equation="ElectronContinuityEquation",
            )
            hole = get_contact_current(
                device=device,
                contact=contact,
                equation="HoleContinuityEquation",
            )
            currents[contact] = electron + hole
        points.append({"bias_v": bias, "converged": True, "currents_a_per_cm2": currents})

    positions_cm = get_node_model_values(device=device, region=region, name="x")
    fields: dict[str, dict[str, Any]] = {}
    field_models = {
        "potential": ("Potential", "V"),
        "electron_density": ("Electrons", "cm^-3"),
        "hole_density": ("Holes", "cm^-3"),
        "net_doping": ("NetDoping", "cm^-3"),
    }
    for output_name, (model_name, unit) in field_models.items():
        if output_name in payload["observables"] or output_name == "net_doping":
            fields[output_name] = {
                "positions_cm": list(positions_cm),
                "values": list(
                    get_node_model_values(device=device, region=region, name=model_name)
                ),
                "unit": unit,
            }

    result = {
        "schema_version": "1.0",
        "simulator_version": devsim.__version__,
        "status": "completed",
        "terminals": list(payload["contacts"].values()),
        "bias_points": points,
        "fields": fields,
    }
    Path("native_result.json").write_text(json.dumps(result, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
