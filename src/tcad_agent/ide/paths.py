"""Canonical path enforcement for repository-scoped operations."""

from pathlib import Path


class WorkspacePathError(ValueError):
    pass


def canonical_directory(path: Path) -> Path:
    expanded = path.expanduser()
    try:
        if not expanded.exists():
            raise WorkspacePathError(f"workspace path does not exist: {expanded}")
        resolved = expanded.resolve(strict=True)
    except OSError as exc:
        raise WorkspacePathError("workspace path is unavailable") from exc
    if not resolved.is_dir():
        raise WorkspacePathError(f"workspace path is not a directory: {resolved}")
    return resolved


def resolve_workspace_path(root: Path, relative: str) -> Path:
    if Path(relative).is_absolute():
        raise WorkspacePathError("workspace-relative path must not be absolute")
    canonical_root = canonical_directory(root)
    candidate = canonical_root if relative in {"", "."} else canonical_root / relative
    try:
        resolved = candidate.resolve(strict=True)
    except OSError as exc:
        raise WorkspacePathError("workspace entry is unavailable") from exc
    if not resolved.is_relative_to(canonical_root):
        raise WorkspacePathError("path resolves outside the workspace")
    return resolved
