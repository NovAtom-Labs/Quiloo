from pathlib import Path

from tcad_agent.ide.store import SqliteIDEStore
from tcad_agent.ide.workspaces import WorkspaceManager


def test_workspace_survives_store_reconstruction(tmp_path: Path) -> None:
    root = tmp_path / "plain-directory"
    root.mkdir()
    database = tmp_path / "ide.sqlite3"
    created = WorkspaceManager(SqliteIDEStore(database)).open(root)

    reopened = WorkspaceManager(SqliteIDEStore(database)).get(created.id)

    assert reopened.root == root.resolve()
    assert reopened.git.available is False
