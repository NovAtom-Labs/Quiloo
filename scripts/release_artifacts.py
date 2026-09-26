#!/usr/bin/env python3
"""Stage and collect the public Agent Kronig release artifacts."""

from __future__ import annotations

import argparse
import hashlib
import shutil
import sys
from pathlib import Path

PACKAGE_CONTRACTS: dict[tuple[str, str], tuple[str, ...]] = {
    ("linux", "x64"): (".AppImage", ".deb"),
    ("win", "x64"): (".exe", ".zip"),
    ("mac", "x64"): (".dmg", ".zip"),
    ("mac", "arm64"): (".dmg", ".zip"),
}
PUBLIC_SUFFIXES = (".AppImage", ".deb", ".dmg", ".exe", ".sig", ".zip")
_BUILDER_ARCHITECTURES: dict[tuple[str, str, str], tuple[str, ...]] = {
    ("linux", "x64", ".AppImage"): ("x64", "x86_64"),
    ("linux", "x64", ".AppImage.sig"): ("x64", "x86_64"),
    ("linux", "x64", ".deb"): ("x64", "amd64"),
}


def _new_empty_directory(path: Path) -> Path:
    if path.exists():
        if not path.is_dir():
            raise FileExistsError(f"Destination is not a directory: {path}")
        if any(path.iterdir()):
            raise FileExistsError(f"Destination is not empty: {path}")
    else:
        path.mkdir(parents=True)
    return path


def _matching_package(
    source: Path,
    platform: str,
    architecture: str,
    suffix: str,
) -> Path:
    architectures = _BUILDER_ARCHITECTURES.get(
        (platform, architecture, suffix), (architecture,)
    )
    tokens = tuple(f"-{platform}-{item}{suffix}" for item in architectures)
    candidates = sorted(
        path
        for path in source.iterdir()
        if path.name.startswith("Agent-Kronig-")
        and path.name.endswith(tokens)
    )
    if not candidates:
        raise FileNotFoundError(
            f"Required {platform}/{architecture} package is missing: {suffix}"
        )
    if len(candidates) > 1:
        names = ", ".join(path.name for path in candidates)
        raise ValueError(f"Multiple {suffix} packages matched: {names}")
    package = candidates[0]
    if package.is_symlink():
        raise ValueError(f"Release packages cannot be symlinks: {package.name}")
    if not package.is_file():
        raise ValueError(f"Release package is not a regular file: {package.name}")
    return package


def _canonical_package_name(
    package: Path,
    platform: str,
    architecture: str,
    suffix: str,
) -> str:
    architectures = _BUILDER_ARCHITECTURES.get(
        (platform, architecture, suffix), (architecture,)
    )
    for builder_architecture in architectures:
        ending = f"-{platform}-{builder_architecture}{suffix}"
        if package.name.endswith(ending):
            return (
                package.name[: -len(ending)]
                + f"-{platform}-{architecture}{suffix}"
            )
    raise ValueError(f"Package name does not match its release target: {package.name}")


def stage_platform_artifacts(
    source: Path,
    destination: Path,
    platform: str,
    architecture: str,
) -> tuple[Path, ...]:
    """Copy exactly the public packages for one native build target."""

    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Build output directory does not exist: {source}")
    try:
        required_suffixes = PACKAGE_CONTRACTS[(platform, architecture)]
    except KeyError as exc:
        raise ValueError(
            f"Unsupported release target: {platform}/{architecture}"
        ) from exc

    packages = [
        (_matching_package(source, platform, architecture, suffix), suffix)
        for suffix in required_suffixes
    ]
    if (platform, architecture) == ("linux", "x64"):
        signature_suffix = ".AppImage.sig"
        signature_tokens = tuple(
            f"-linux-{item}{signature_suffix}"
            for item in _BUILDER_ARCHITECTURES[("linux", "x64", signature_suffix)]
        )
        signature_candidates = sorted(
            path
            for path in source.iterdir()
            if path.name.startswith("Agent-Kronig-")
            and path.name.endswith(signature_tokens)
        )
        if len(signature_candidates) > 1:
            raise ValueError("Multiple AppImage signatures matched")
        if signature_candidates:
            signature = signature_candidates[0]
            if signature.is_symlink() or not signature.is_file():
                raise ValueError(
                    "Release signature must be a regular file, not a symlink: "
                    f"{signature.name}"
                )
            packages.append((signature, signature_suffix))

    destination = _new_empty_directory(destination)
    staged = []
    normalized_packages = sorted(
        [
            (
                package,
                _canonical_package_name(
                    package, platform, architecture, suffix
                ),
            )
            for package, suffix in packages
        ],
        key=lambda item: item[1],
    )
    for package, public_name in normalized_packages:
        target = destination / public_name
        shutil.copy2(package, target)
        staged.append(target)
    return tuple(staged)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def collect_release_artifacts(
    source: Path,
    destination: Path,
) -> tuple[Path, ...]:
    """Flatten staged build artifacts and create a deterministic checksum file."""

    source = source.resolve()
    if not source.is_dir():
        raise FileNotFoundError(f"Downloaded artifacts directory does not exist: {source}")

    packages: dict[str, Path] = {}
    for candidate in sorted(source.rglob("*")):
        if candidate.is_symlink():
            if candidate.name.endswith(PUBLIC_SUFFIXES):
                raise ValueError(
                    f"Release packages cannot be symlinks: {candidate.name}"
                )
            continue
        if not candidate.is_file() or not candidate.name.endswith(PUBLIC_SUFFIXES):
            continue
        if candidate.name in packages:
            raise FileExistsError(f"Duplicate release filename: {candidate.name}")
        packages[candidate.name] = candidate
    if not packages:
        raise FileNotFoundError("No public release artifacts were found")

    destination = _new_empty_directory(destination)
    collected: list[Path] = []
    for name in sorted(packages):
        target = destination / name
        shutil.copy2(packages[name], target)
        collected.append(target)

    checksum_path = destination / "SHA256SUMS.txt"
    checksum_path.write_text(
        "".join(f"{_sha256(path)}  {path.name}\n" for path in collected)
    )
    return (*collected, checksum_path)


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    stage = subparsers.add_parser("stage")
    stage.add_argument("source", type=Path)
    stage.add_argument("destination", type=Path)
    stage.add_argument("platform")
    stage.add_argument("architecture")

    collect = subparsers.add_parser("collect")
    collect.add_argument("source", type=Path)
    collect.add_argument("destination", type=Path)

    arguments = parser.parse_args()
    try:
        if arguments.command == "stage":
            outputs = stage_platform_artifacts(
                arguments.source,
                arguments.destination,
                arguments.platform,
                arguments.architecture,
            )
        else:
            outputs = collect_release_artifacts(
                arguments.source,
                arguments.destination,
            )
    except (OSError, ValueError) as exc:
        print(f"Release artifact preparation failed: {exc}", file=sys.stderr)
        return 2
    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
