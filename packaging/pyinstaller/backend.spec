# -*- mode: python ; coding: utf-8 -*-
from pathlib import Path
from importlib.metadata import distribution, packages_distributions

from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

from PyInstaller.utils.hooks import (
    collect_all,
    collect_data_files,
    collect_submodules,
    copy_metadata,
)

project_root = Path.cwd()
source_package = project_root / "src" / "tcad_agent"
package_datas = [(str(source_package), "tcad_agent")]
openhands_datas, openhands_binaries, openhands_hidden = collect_all("openhands")


def active_dependency_graph(seeds):
    pending = list(seeds)
    selected = set()
    while pending:
        requested = pending.pop()
        name = canonicalize_name(requested)
        if name in selected:
            continue
        selected.add(name)
        for requirement_text in distribution(requested).requires or ():
            requirement = Requirement(requirement_text)
            if requirement.marker is not None and not requirement.marker.evaluate():
                continue
            pending.append(requirement.name)
    return selected


dependency_names = active_dependency_graph(
    ("novatom-tcad-agent", "openhands-sdk", "openhands-tools")
)
distribution_metadata = []
dependency_datas = []
for dependency_name in sorted(dependency_names):
    distribution_metadata += copy_metadata(dependency_name)
for package_name, owning_distributions in packages_distributions().items():
    if package_name == "tcad_agent":
        continue
    if any(canonicalize_name(name) in dependency_names for name in owning_distributions):
        dependency_datas += collect_data_files(package_name, include_py_files=True)

analysis = Analysis(
    [str(project_root / "src" / "tcad_agent" / "desktop" / "server.py")],
    pathex=[str(project_root / "src")],
    binaries=openhands_binaries,
    datas=(
        package_datas
        + openhands_datas
        + dependency_datas
        + distribution_metadata
    ),
    hiddenimports=(
        collect_submodules("tcad_agent")
        + openhands_hidden
        + ["tiktoken_ext.openai_public"]
    ),
    hookspath=[],
    runtime_hooks=[],
    excludes=["devsim"],
    noarchive=False,
)
archive = PYZ(analysis.pure)
executable = EXE(
    archive,
    analysis.scripts,
    [],
    exclude_binaries=True,
    name="agent-kronig-backend",
    console=True,
)
collection = COLLECT(
    executable,
    analysis.binaries,
    analysis.datas,
    strip=False,
    upx=False,
    name="agent-kronig-backend",
)
