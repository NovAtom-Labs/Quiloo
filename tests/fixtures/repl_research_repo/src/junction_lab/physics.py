"""Analytical semiconductor quantities in SI units."""

from __future__ import annotations

import math

from junction_lab.config import Experiment

BOLTZMANN_EV_PER_K = 8.617333262e-5
ELEMENTARY_CHARGE_C = 1.602176634e-19
VACUUM_PERMITTIVITY_F_PER_M = 8.8541878128e-12
CM3_TO_M3 = 1.0e6


def built_in_potential_v(experiment: Experiment) -> float:
    thermal_voltage_v = BOLTZMANN_EV_PER_K * experiment.temperature_k
    ratio = (
        experiment.acceptor_cm3
        * experiment.donor_cm3
        / experiment.intrinsic_density_cm3**2
    )
    return thermal_voltage_v * math.log(ratio)


def depletion_width_m(experiment: Experiment, potential_v: float) -> float:
    acceptor_m3 = experiment.acceptor_cm3 * CM3_TO_M3
    donor_m3 = experiment.donor_cm3 * CM3_TO_M3
    permittivity = experiment.relative_permittivity * VACUUM_PERMITTIVITY_F_PER_M
    return math.sqrt(
        2.0
        * permittivity
        * potential_v
        / ELEMENTARY_CHARGE_C
        * (1.0 / acceptor_m3 + 1.0 / donor_m3)
    )


def peak_electric_field_v_per_m(potential_v: float, width_m: float) -> float:
    return (2.0 * potential_v / width_m) / 100.0


def summarize(experiment: Experiment) -> dict[str, float | str]:
    potential = built_in_potential_v(experiment)
    width = depletion_width_m(experiment, potential)
    return {
        "experiment": experiment.name,
        "temperature_k": experiment.temperature_k,
        "built_in_potential_v": potential,
        "depletion_width_m": width,
        "peak_electric_field_v_per_m": peak_electric_field_v_per_m(
            potential, width
        ),
        "equilibrium_current_density_a_per_m2": 0.0,
        "model_version": experiment.model_version,
    }
