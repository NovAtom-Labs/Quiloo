import pytest

from tcad_agent.results.models import FieldSeries
from tcad_agent.validation.mesh import compare_mesh_results


def field(positions: tuple[float, ...], values: tuple[float, ...]) -> FieldSeries:
    return FieldSeries(positions_m=positions, values=values, unit="V")


def test_mesh_comparison_interpolates_onto_shared_coordinates() -> None:
    comparison = compare_mesh_results(
        field((0.0, 1.0), (0.0, 1.0)),
        field((0.0, 0.5, 1.0), (0.0, 0.5, 1.0)),
        tolerance=1e-9,
        field="potential",
    )
    assert comparison.field == "potential"
    assert comparison.relative_linf == pytest.approx(0.0)
    assert comparison.stable is True


def test_mesh_comparison_marks_material_change_unstable() -> None:
    comparison = compare_mesh_results(
        field((0.0, 1.0), (0.0, 1.0)),
        field((0.0, 0.5, 1.0), (0.0, 0.8, 1.0)),
        tolerance=0.1,
    )
    assert comparison.relative_linf == pytest.approx(0.3)
    assert comparison.stable is False


def test_mesh_comparison_rejects_nonoverlapping_domains() -> None:
    with pytest.raises(ValueError, match="overlap"):
        compare_mesh_results(
            field((0.0, 1.0), (0.0, 1.0)),
            field((2.0, 3.0), (2.0, 3.0)),
            tolerance=0.1,
        )
