"""Scientific acceptance checks."""


def relative_error(measured: float, expected: float) -> float:
    if expected == 0.0:
        return abs(measured)
    return abs(measured - expected) / abs(expected)


def within_relative_tolerance(
    measured: float,
    expected: float,
    tolerance_fraction: float,
) -> bool:
    return relative_error(measured, expected) <= tolerance_fraction * 0.01
