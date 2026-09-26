"""Ephemeral, process-scoped storage for the desktop agent runtime."""

from __future__ import annotations

import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path


class DesktopSessionStorageError(RuntimeError):
    """Raised when private desktop session storage cannot be prepared safely."""


_ERROR_MESSAGE = "Agent Kronig could not prepare private session storage."
_SESSIONS_DIRECTORY = "sessions"
_MIGRATION_MARKER = "repository-memory-removed-v1"
_LEGACY_PATHS = (
    "ide.sqlite3",
    "ide.sqlite3-wal",
    "ide.sqlite3-shm",
    "openhands",
)


def _require_contained(path: Path, parent: Path) -> Path:
    if path.is_symlink():
        raise DesktopSessionStorageError(_ERROR_MESSAGE)
    resolved = path.resolve()
    try:
        resolved.relative_to(parent)
    except ValueError as exc:
        raise DesktopSessionStorageError(_ERROR_MESSAGE) from exc
    return resolved


def _remove_contained(path: Path, parent: Path) -> None:
    if not path.exists() and not path.is_symlink():
        return
    target = _require_contained(path, parent)
    if target.is_dir():
        shutil.rmtree(target)
    else:
        target.unlink()


@dataclass(frozen=True)
class DesktopSessionStorage:
    """Own one temporary runtime root beneath the locked desktop data path."""

    data_dir: Path
    runtime_root: Path

    @classmethod
    def prepare(cls, data_dir: Path) -> DesktopSessionStorage:
        """Remove stale private state and create a fresh process runtime root."""

        try:
            data_dir.mkdir(parents=True, exist_ok=True)
            resolved_data_dir = data_dir.resolve()
            sessions = resolved_data_dir / _SESSIONS_DIRECTORY
            if sessions.is_symlink():
                raise DesktopSessionStorageError(_ERROR_MESSAGE)
            sessions.mkdir(mode=0o700, exist_ok=True)
            resolved_sessions = _require_contained(sessions, resolved_data_dir)

            for child in tuple(resolved_sessions.iterdir()):
                _remove_contained(child, resolved_sessions)

            marker = resolved_data_dir / _MIGRATION_MARKER
            if not marker.exists():
                for name in _LEGACY_PATHS:
                    _remove_contained(resolved_data_dir / name, resolved_data_dir)
                marker.touch(mode=0o600)

            runtime_root = Path(
                tempfile.mkdtemp(prefix="session-", dir=resolved_sessions)
            ).resolve()
            runtime_root.chmod(0o700)
            return cls(data_dir=resolved_data_dir, runtime_root=runtime_root)
        except DesktopSessionStorageError:
            raise
        except OSError as exc:
            raise DesktopSessionStorageError(_ERROR_MESSAGE) from exc

    def cleanup(self) -> None:
        """Delete only this process's runtime root."""

        try:
            sessions = _require_contained(
                self.data_dir / _SESSIONS_DIRECTORY,
                self.data_dir,
            )
            _remove_contained(self.runtime_root, sessions)
        except DesktopSessionStorageError:
            raise
        except OSError as exc:
            raise DesktopSessionStorageError(_ERROR_MESSAGE) from exc
