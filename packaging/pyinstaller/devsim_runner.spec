# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules
from scripts.package_windows_math import collect_windows_math_binaries

project_root = Path.cwd()
devsim_datas, devsim_binaries, devsim_hidden = collect_all("devsim")
math_binaries = collect_windows_math_binaries()
runtime_source = project_root / "src" / "tcad_agent" / "adapters" / "devsim" / "runtime.py"
source_package = project_root / "src" / "tcad_agent"

analysis = Analysis(
    [str(project_root / "src" / "tcad_agent" / "desktop" / "devsim_runner.py")],
    pathex=[str(project_root / "src")],
    binaries=devsim_binaries + math_binaries,
    datas=(
        [(str(source_package), "tcad_agent")]
        + devsim_datas
        + [(str(runtime_source), "tcad_agent/adapters/devsim")]
    ),
    hiddenimports=collect_submodules("tcad_agent.adapters.devsim") + devsim_hidden,
    hookspath=[],
    runtime_hooks=[],
    excludes=["openhands", "fastembed"],
    noarchive=False,
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="agent-kronig-devsim",
    console=True,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="agent-kronig-devsim",
)
