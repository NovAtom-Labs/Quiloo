from pathlib import Path

import pytest

from tcad_agent.desktop.session_storage import (
    DesktopSessionStorage,
    DesktopSessionStorageError,
)


def test_prepare_creates_unique_runtime_root_beneath_session_area(
    tmp_path: Path,
) -> None:
    first = DesktopSessionStorage.prepare(tmp_path)
    first.cleanup()
    second = DesktopSessionStorage.prepare(tmp_path)

    assert first.runtime_root.parent == tmp_path.resolve() / "sessions"
    assert second.runtime_root.parent == tmp_path.resolve() / "sessions"
    assert first.runtime_root != second.runtime_root
    assert second.runtime_root.is_dir()
    second.cleanup()


def test_cleanup_removes_only_the_current_runtime_root(tmp_path: Path) -> None:
    storage = DesktopSessionStorage.prepare(tmp_path)
    sibling = storage.runtime_root.parent / "unrelated"
    sibling.mkdir()
    (sibling / "sentinel.txt").write_text("keep", encoding="utf-8")

    storage.cleanup()

    assert not storage.runtime_root.exists()
    assert (sibling / "sentinel.txt").read_text(encoding="utf-8") == "keep"


def test_prepare_removes_stale_runtime_roots_after_lock_acquisition(
    tmp_path: Path,
) -> None:
    stale = tmp_path / "sessions" / "stale-process"
    stale.mkdir(parents=True)
    (stale / "ide.sqlite3").write_text("stale", encoding="utf-8")

    storage = DesktopSessionStorage.prepare(tmp_path)

    assert not stale.exists()
    assert storage.runtime_root.is_dir()
    storage.cleanup()


def test_prepare_rejects_symlinked_session_area_that_escapes_data_dir(
    tmp_path: Path,
) -> None:
    external = tmp_path.parent / f"{tmp_path.name}-external"
    external.mkdir()
    (tmp_path / "sessions").symlink_to(external, target_is_directory=True)

    with pytest.raises(DesktopSessionStorageError, match="private session storage"):
        DesktopSessionStorage.prepare(tmp_path)

    assert external.is_dir()


def test_legacy_cleanup_removes_ide_database_sidecars_and_openhands_memory(
    tmp_path: Path,
) -> None:
    for name in ("ide.sqlite3", "ide.sqlite3-wal", "ide.sqlite3-shm"):
        (tmp_path / name).write_text("legacy", encoding="utf-8")
    openhands = tmp_path / "openhands" / "conversation-id"
    openhands.mkdir(parents=True)
    (openhands / "events.jsonl").write_text("legacy", encoding="utf-8")

    storage = DesktopSessionStorage.prepare(tmp_path)

    assert all(
        not (tmp_path / name).exists()
        for name in ("ide.sqlite3", "ide.sqlite3-wal", "ide.sqlite3-shm", "openhands")
    )
    assert (tmp_path / "repository-memory-removed-v1").is_file()
    storage.cleanup()


def test_legacy_cleanup_is_idempotent_when_paths_are_missing(tmp_path: Path) -> None:
    first = DesktopSessionStorage.prepare(tmp_path)
    first.cleanup()

    second = DesktopSessionStorage.prepare(tmp_path)

    assert (tmp_path / "repository-memory-removed-v1").is_file()
    second.cleanup()


def test_legacy_cleanup_never_removes_settings_credentials_or_repository_files(
    tmp_path: Path,
) -> None:
    repository = tmp_path.parent / f"{tmp_path.name}-repository"
    repository.mkdir()
    repository_sentinel = repository / "device.py"
    repository_sentinel.write_text("preserve", encoding="utf-8")
    preserved = {
        "settings.json": "settings",
        "secrets.bin": "credentials",
        "requests.sqlite3": "requests",
    }
    for name, value in preserved.items():
        (tmp_path / name).write_text(value, encoding="utf-8")
    (tmp_path / "ide.sqlite3").write_text("legacy", encoding="utf-8")

    storage = DesktopSessionStorage.prepare(tmp_path)

    for name, value in preserved.items():
        assert (tmp_path / name).read_text(encoding="utf-8") == value
    assert repository_sentinel.read_text(encoding="utf-8") == "preserve"
    storage.cleanup()


def test_legacy_cleanup_failure_is_sanitized_and_stops_startup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    legacy = tmp_path / "ide.sqlite3"
    legacy.write_text("legacy", encoding="utf-8")
    original_unlink = Path.unlink

    def fail_legacy_unlink(path: Path, *args: object, **kwargs: object) -> None:
        if path == legacy:
            raise OSError("private filesystem detail")
        original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", fail_legacy_unlink)

    with pytest.raises(DesktopSessionStorageError) as exc_info:
        DesktopSessionStorage.prepare(tmp_path)

    assert str(exc_info.value) == "Agent Kronig could not prepare private session storage."
    assert "private filesystem detail" not in str(exc_info.value)
    assert not (tmp_path / "repository-memory-removed-v1").exists()
