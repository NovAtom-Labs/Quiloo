"""Conversation service for persistent repository tasks."""

from uuid import UUID

from tcad_agent.ide.events import EventFeed
from tcad_agent.ide.models import ConversationMessage, ConversationRecord
from tcad_agent.ide.store import SqliteIDEStore


class ConversationInputError(ValueError):
    pass


def _normalized_text(value: str, *, label: str, maximum: int) -> str:
    normalized = value.strip()
    if not normalized:
        raise ConversationInputError(f"{label} must not be empty")
    if len(normalized) > maximum:
        raise ConversationInputError(f"{label} must not exceed {maximum} characters")
    return normalized


class ConversationService:
    def __init__(self, store: SqliteIDEStore, events: EventFeed) -> None:
        self.store = store
        self.events = events

    def create(self, workspace_id: UUID, title: str) -> ConversationRecord:
        self.store.get_workspace(workspace_id)
        conversation = self.store.create_conversation(
            workspace_id,
            _normalized_text(title, label="conversation title", maximum=120),
        )
        self.events.append(
            conversation.id,
            "conversation_created",
            {"workspace_id": str(workspace_id)},
        )
        return conversation

    def list(self, workspace_id: UUID) -> tuple[ConversationRecord, ...]:
        self.store.get_workspace(workspace_id)
        return self.store.list_conversations(workspace_id)

    def get(self, conversation_id: UUID) -> ConversationRecord:
        return self.store.get_conversation(conversation_id)

    def add_user_message(
        self, conversation_id: UUID, content: str
    ) -> ConversationMessage:
        message = self.store.append_message(
            conversation_id,
            "user",
            _normalized_text(content, label="message", maximum=100_000),
        )
        self.events.append(
            conversation_id,
            "message_created",
            {"message_id": str(message.id), "role": message.role},
        )
        return message

    def add_assistant_message(
        self, conversation_id: UUID, content: str
    ) -> ConversationMessage:
        message = self.store.append_message(
            conversation_id,
            "assistant",
            _normalized_text(content, label="message", maximum=100_000),
        )
        self.events.append(
            conversation_id,
            "message_created",
            {"message_id": str(message.id), "role": message.role},
        )
        return message

    def messages(
        self, conversation_id: UUID
    ) -> tuple[ConversationMessage, ...]:
        return self.store.list_messages(conversation_id)
