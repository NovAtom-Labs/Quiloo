from pathlib import Path

from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def test_reopening_same_canonical_directory_reuses_workspace(tmp_path: Path) -> None:
    root = tmp_path / "repo"
    root.mkdir()
    alias = tmp_path / "repo-alias"
    alias.symlink_to(root, target_is_directory=True)
    manager = WorkspaceManager(SqliteIDEStore(tmp_path / "ide.sqlite3"))

    first = manager.open(root)
    second = manager.open(alias)

    assert second.id == first.id
    assert second.revision == first.revision + 1
    assert manager.list() == (second,)
