"""Application service for opening and inspecting local workspaces."""

from pathlib import Path
from uuid import UUID

from tcad_agent.ide.models import WorkspaceEntry, WorkspaceRecord
from tcad_agent.ide.repository import RepositoryInspector
from tcad_agent.ide.store import SqliteIDEStore


class WorkspaceManager:
    def __init__(
        self,
        store: SqliteIDEStore,
        inspector: RepositoryInspector | None = None,
    ) -> None:
        self.store = store
        self.inspector = inspector or RepositoryInspector()

    def open(self, path: Path) -> WorkspaceRecord:
        return self.store.open_workspace(self.inspector.inspect(path))

    def list(self) -> tuple[WorkspaceRecord, ...]:
        return self.store.list_workspaces()

    def get(self, workspace_id: UUID) -> WorkspaceRecord:
        return self.store.get_workspace(workspace_id)

    def entries(
        self, workspace_id: UUID, relative: str = "."
    ) -> tuple[WorkspaceEntry, ...]:
        workspace = self.get(workspace_id)
        return self.inspector.entries(workspace.root, relative)
