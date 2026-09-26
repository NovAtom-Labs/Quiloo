from pathlib import Path

import pytest

from tcad_agent.desktop.lock import DataDirectoryLock, DesktopDataLockError


def test_data_directory_lock_blocks_competing_backend_and_releases(tmp_path: Path) -> None:
    first = DataDirectoryLock(tmp_path)
    first.acquire()

    competing = DataDirectoryLock(tmp_path)
    with pytest.raises(DesktopDataLockError, match="already in use"):
        competing.acquire()

    first.close()
    competing.acquire()
    competing.close()


def test_data_directory_lock_context_records_current_process(tmp_path: Path) -> None:
    with DataDirectoryLock(tmp_path) as lock:
        assert lock.acquired
    contents = lock.path.read_text(encoding="utf-8")

    assert contents.startswith("pid=")
    assert not lock.acquired
