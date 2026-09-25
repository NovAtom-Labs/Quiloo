"""Cross-platform advisory lock for the mutable desktop data directory."""

from __future__ import annotations

import os
from pathlib import Path
from types import TracebackType
from typing import Any, TextIO, cast


class DesktopDataLockError(RuntimeError):
    """Raised when another backend owns the desktop data directory."""


class DataDirectoryLock:
    """Hold an operating-system advisory lock for one backend lifetime."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = data_dir
        self.path = data_dir / "backend.lock"
        self._file: TextIO | None = None

    @property
    def acquired(self) -> bool:
        return self._file is not None

    def acquire(self) -> None:
        if self._file is not None:
            return
        self.data_dir.mkdir(parents=True, exist_ok=True)
        handle = self.path.open("a+", encoding="utf-8")
        try:
            self._acquire_file(handle)
        except OSError as exc:
            handle.close()
            raise DesktopDataLockError(
                f"Agent Kronig data directory is already in use: {self.data_dir}"
            ) from exc
        handle.seek(0)
        handle.truncate()
        handle.write(f"pid={os.getpid()}\n")
        handle.flush()
        self._file = handle

    def close(self) -> None:
        handle = self._file
        if handle is None:
            return
        self._file = None
        try:
            self._release_file(handle)
        finally:
            handle.close()

    def __enter__(self) -> DataDirectoryLock:
        self.acquire()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        traceback: TracebackType | None,
    ) -> None:
        del exc_type, exc, traceback
        self.close()

    @staticmethod
    def _acquire_file(handle: TextIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            if not handle.read(1):
                handle.write("\0")
                handle.flush()
            handle.seek(0)
            windows_lock = cast(Any, msvcrt)
            windows_lock.locking(handle.fileno(), windows_lock.LK_NBLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

    @staticmethod
    def _release_file(handle: TextIO) -> None:
        if os.name == "nt":
            import msvcrt

            handle.seek(0)
            windows_lock = cast(Any, msvcrt)
            windows_lock.locking(handle.fileno(), windows_lock.LK_UNLCK, 1)
            return

        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
