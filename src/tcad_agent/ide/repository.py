"""Bounded Git and directory inspection for local workspaces."""

import subprocess
from pathlib import Path

from tcad_agent.ide.models import GitSnapshot, RepositorySnapshot, WorkspaceEntry
from tcad_agent.ide.paths import (
    WorkspacePathError,
    canonical_directory,
    resolve_workspace_path,
)


class RepositoryInspector:
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
