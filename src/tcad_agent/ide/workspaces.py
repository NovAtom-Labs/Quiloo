"""Application service for opening and inspecting local workspaces."""

from pathlib import Path
from uuid import UUID

from tcad_agent.ide.models import (
    WorkspaceEntry,
    WorkspaceFilePreview,
    WorkspaceRecord,
    WorkspaceTextFile,
)
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

    def preview_file(
        self, workspace_id: UUID, relative: str
    ) -> WorkspaceFilePreview:
        workspace = self.get(workspace_id)
        return self.inspector.preview_file(workspace.root, relative)

    def file_path(self, workspace_id: UUID, relative: str) -> Path:
        workspace = self.get(workspace_id)
        return self.inspector.file_path(workspace.root, relative)

    def editable_file(self, workspace_id: UUID, relative: str) -> WorkspaceTextFile:
        workspace = self.get(workspace_id)
        return self.inspector.editable_file(workspace.root, relative)

    def save_editable_file(
        self,
        workspace_id: UUID,
        relative: str,
        content: str,
        expected_sha256: str,
    ) -> WorkspaceTextFile:
        workspace = self.get(workspace_id)
        return self.inspector.save_editable_file(
            workspace.root, relative, content, expected_sha256
        )
