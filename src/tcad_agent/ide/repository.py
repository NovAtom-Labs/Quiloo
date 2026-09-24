"""Bounded Git and directory inspection for local workspaces."""

import json
import mimetypes
import subprocess
from pathlib import Path

from tcad_agent.ide.models import (
    GitSnapshot,
    RepositorySnapshot,
    WorkspaceEntry,
    WorkspaceFileKind,
    WorkspaceFilePreview,
)
from tcad_agent.ide.paths import (
    WorkspacePathError,
    canonical_directory,
    resolve_workspace_path,
)


class RepositoryInspector:
    preview_limit = 1024 * 1024

    def inspect(self, root: Path) -> RepositorySnapshot:
        canonical_root = canonical_directory(root)
        return RepositorySnapshot(
            root=canonical_root,
            display_name=canonical_root.name,
            git=self._git_snapshot(canonical_root),
        )

    def entries(
        self, root: Path, relative: str = "."
    ) -> tuple[WorkspaceEntry, ...]:
        canonical_root = canonical_directory(root)
        target = resolve_workspace_path(canonical_root, relative)
        if not target.is_dir():
            raise WorkspacePathError("workspace entry is not a directory")
        rows: list[WorkspaceEntry] = []
        try:
            for child in target.iterdir():
                child_relative = child.relative_to(canonical_root).as_posix()
                if child.is_symlink():
                    rows.append(
                        WorkspaceEntry(
                            path=child_relative,
                            name=child.name,
                            kind="symlink",
                        )
                    )
                elif child.is_dir():
                    rows.append(
                        WorkspaceEntry(
                            path=child_relative,
                            name=child.name,
                            kind="directory",
                        )
                    )
                elif child.is_file():
                    rows.append(
                        WorkspaceEntry(
                            path=child_relative,
                            name=child.name,
                            kind="file",
                            size=child.stat().st_size,
                        )
                    )
        except OSError as exc:
            raise WorkspacePathError("workspace entry is unavailable") from exc
        order = {"directory": 0, "file": 1, "symlink": 2}
        return tuple(
            sorted(rows, key=lambda row: (order[row.kind], row.name.casefold()))
        )

    def file_path(self, root: Path, relative: str) -> Path:
        canonical_root = canonical_directory(root)
        target = resolve_workspace_path(canonical_root, relative)
        if not target.is_file():
            raise WorkspacePathError("workspace entry is not a file")
        return target

    def preview_file(self, root: Path, relative: str) -> WorkspaceFilePreview:
        canonical_root = canonical_directory(root)
        target = self.file_path(canonical_root, relative)
        normalized = target.relative_to(canonical_root).as_posix()
        size = target.stat().st_size
        mime_type = self._mime_type(target)
        kind = self._preview_kind(target, mime_type)
        if kind in {"image", "pdf"}:
            return WorkspaceFilePreview(
                path=normalized,
                name=target.name,
                kind=kind,
                mime_type=mime_type,
                size=size,
            )

        with target.open("rb") as stream:
            raw = stream.read(self.preview_limit + 1)
        truncated = len(raw) > self.preview_limit
        raw = raw[: self.preview_limit]
        if b"\x00" in raw:
            return WorkspaceFilePreview(
                path=normalized,
                name=target.name,
                kind="binary",
                mime_type="application/octet-stream",
                size=size,
            )
        if kind == "binary":
            try:
                content = raw.decode("utf-8")
            except UnicodeDecodeError:
                return WorkspaceFilePreview(
                    path=normalized,
                    name=target.name,
                    kind="binary",
                    mime_type="application/octet-stream",
                    size=size,
                )
            kind = "text"
            mime_type = "text/plain"
        else:
            content = raw.decode("utf-8", errors="replace")
        if kind == "json" and not truncated:
            try:
                content = json.dumps(
                    json.loads(content), indent=2, ensure_ascii=False
                )
            except json.JSONDecodeError:
                pass
        return WorkspaceFilePreview(
            path=normalized,
            name=target.name,
            kind=kind,
            mime_type=mime_type,
            size=size,
            truncated=truncated,
            content=content,
        )

    @staticmethod
    def _mime_type(path: Path) -> str:
        suffix = path.suffix.casefold()
        overrides = {
            ".md": "text/markdown",
            ".markdown": "text/markdown",
            ".json": "application/json",
            ".csv": "text/csv",
            ".tsv": "text/tab-separated-values",
        }
        return (
            overrides.get(suffix)
            or mimetypes.guess_type(path.name)[0]
            or "application/octet-stream"
        )

    @staticmethod
    def _preview_kind(path: Path, mime_type: str) -> WorkspaceFileKind:
        suffix = path.suffix.casefold()
        if suffix in {".md", ".markdown"}:
            return "markdown"
        if suffix in {".json", ".ipynb"}:
            return "json"
        if suffix == ".csv":
            return "csv"
        if suffix == ".tsv":
            return "tsv"
        if mime_type in {"image/png", "image/jpeg", "image/webp", "image/gif"}:
            return "image"
        if mime_type == "application/pdf":
            return "pdf"
        if mime_type.startswith("text/") or suffix in {
            ".py", ".js", ".ts", ".tsx", ".jsx", ".css", ".html",
            ".xml", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".sh",
            ".tcl", ".cmd", ".log", ".dat", ".txt", ".rst",
        }:
            return "text"
        return "binary"

    @staticmethod
    def _git_snapshot(root: Path) -> GitSnapshot:
        def run(*arguments: str) -> subprocess.CompletedProcess[str]:
            return subprocess.run(
                ["git", *arguments],
                shell=False,
                cwd=root,
                timeout=2,
                check=False,
                capture_output=True,
                text=True,
            )

        try:
            git_root = run("rev-parse", "--show-toplevel")
            if git_root.returncode != 0:
                return GitSnapshot(available=False)
            branch = run("branch", "--show-current")
            status = run("status", "--porcelain=v1")
        except (OSError, subprocess.TimeoutExpired):
            return GitSnapshot(available=False)
        return GitSnapshot(
            available=True,
            root=Path(git_root.stdout.strip()).resolve(),
            branch=branch.stdout.strip() or None,
            dirty=bool(status.stdout.strip()),
        )
