"""Mesh-refinement comparison over canonical one-dimensional fields."""

import numpy as np
from pydantic import Field

from tcad_agent.domain.models import StrictModel
from tcad_agent.results.models import FieldSeries


class MeshComparison(StrictModel):
    field: str
    relative_linf: float = Field(ge=0)
    tolerance: float = Field(ge=0)
    stable: bool


def compare_mesh_results(
    coarse: FieldSeries,
    refined: FieldSeries,
    tolerance: float,
    *,
    field: str = "field",
    absolute_floor: float = 1e-30,
) -> MeshComparison:
    if tolerance < 0:
        raise ValueError("mesh comparison tolerance must be nonnegative")
    if absolute_floor <= 0:
        raise ValueError("mesh comparison absolute floor must be positive")
    if coarse.unit != refined.unit:
        raise ValueError("mesh comparison requires matching field units")
    _validate_series(coarse)
    _validate_series(refined)
    overlap_start = max(coarse.positions_m[0], refined.positions_m[0])
    overlap_stop = min(coarse.positions_m[-1], refined.positions_m[-1])
    if overlap_stop < overlap_start:
        raise ValueError("mesh comparison domains do not overlap")
    coordinates = np.unique(
        np.asarray(
            [
                value
                for value in (*coarse.positions_m, *refined.positions_m)
                if overlap_start <= value <= overlap_stop
            ],
            dtype=float,
        )
    )
    coarse_values = np.interp(coordinates, coarse.positions_m, coarse.values)
    refined_values = np.interp(coordinates, refined.positions_m, refined.values)
    delta = float(np.max(np.abs(coarse_values - refined_values)))
    scale = max(float(np.max(np.abs(refined_values))), absolute_floor)
    relative_linf = delta / scale
    return MeshComparison(
        field=field,
        relative_linf=relative_linf,
        tolerance=tolerance,
        stable=relative_linf <= tolerance,
    )


def _validate_series(series: FieldSeries) -> None:
    if not series.positions_m or len(series.positions_m) != len(series.values):
        raise ValueError("mesh field positions and values must have equal nonzero length")
    if any(
        right <= left
        for left, right in zip(series.positions_m, series.positions_m[1:], strict=False)
    ):
        raise ValueError("mesh field coordinates must be strictly increasing")
