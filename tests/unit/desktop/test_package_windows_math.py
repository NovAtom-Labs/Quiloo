from __future__ import annotations

from pathlib import Path

from scripts.package_windows_math import collect_windows_math_binaries


def test_windows_math_collector_packages_every_runtime_dll(tmp_path: Path) -> None:
    runtime_directory = tmp_path / "Library" / "bin"
    runtime_directory.mkdir(parents=True)
    first = runtime_directory / "mkl_rt.2.dll"
    second = runtime_directory / "libiomp5md.dll"
    first.write_bytes(b"mkl")
    second.write_bytes(b"openmp")
    (runtime_directory / "ignored.txt").write_text("no")

    binaries = collect_windows_math_binaries(tmp_path, platform_name="win32")

    assert binaries == [
        (str(second), "math-runtime"),
        (str(first), "math-runtime"),
    ]


def test_math_collector_is_empty_on_other_platforms(tmp_path: Path) -> None:
    assert collect_windows_math_binaries(tmp_path, platform_name="darwin") == []
