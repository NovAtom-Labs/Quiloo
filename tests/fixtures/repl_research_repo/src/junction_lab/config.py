"""Typed experiment loading from the researcher-owned TOML file."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Experiment:
    name: str
    temperature_k: float
    relative_permittivity: float
    intrinsic_density_cm3: float
    acceptor_cm3: float
    donor_cm3: float
    reference_built_in_potential_v: float
    built_in_relative_tolerance: float
    method: str
    model_version: str


def load_experiment(path: Path) -> Experiment:
    document = tomllib.loads(path.read_text())
    return Experiment(
        name=str(document["device"]["name"]),
        temperature_k=float(document["device"]["temperature_k"]),
        relative_permittivity=float(document["material"]["relative_permittivity"]),
        intrinsic_density_cm3=float(document["material"]["intrinsic_density_cm3"]),
        acceptor_cm3=float(document["doping"]["acceptor_cm3"]),
        donor_cm3=float(document["doping"]["donor_cm3"]),
        reference_built_in_potential_v=float(
            document["validation"]["reference_built_in_potential_v"]
        ),
        built_in_relative_tolerance=float(
            document["validation"]["built_in_relative_tolerance"]
        ),
        method=str(document["provenance"]["method"]),
        model_version=str(document["provenance"]["model_version"]),
    )
