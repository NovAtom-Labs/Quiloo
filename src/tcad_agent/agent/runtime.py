"""OpenHands production profile for the local repository agent."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from openhands.sdk import LLM, Agent, AgentContext, Tool
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.event import Event
from openhands.sdk.security import ConfirmRisky, SecurityRisk
from openhands.sdk.skills import load_skills_from_dir
from openhands.sdk.subagent import register_file_agents
from openhands.sdk.tool import ToolDefinition, register_tool
from openhands.tools.preset.default import (
    get_default_condenser,
    get_default_tools,
    register_builtins_agents,
)
from openhands.tools.task import TaskToolSet
from openhands.tools.task.manager import ConfirmationHandler
from pydantic import SecretStr

from tcad_agent.agent.policy import WorkspaceSecurityAnalyzer, classify_action
from tcad_agent.agent.supervisor import RuntimeConversation
from tcad_agent.agent.tools import DomainTools, TcadDomainTool, build_tools
from tcad_agent.ide.models import PermissionCategory

DEFAULT_LLM_MODEL = "bedrock/global.anthropic.claude-sonnet-4-6"
DEFAULT_AWS_REGION = "ap-south-1"
PROJECT_ROOT = Path(__file__).resolve().parents[3]


class ModelConfigurationError(RuntimeError):
    pass


def llm_from_environment() -> LLM:
    """Build the Bedrock LLM client from environment variables.

    Shared by the IDE agent runtime and the structured proposal gateway so the
    credential, region, and model resolution can't drift between them again.
    """
    token = os.getenv("AWS_BEARER_TOKEN_BEDROCK")
    if not token:
        raise ModelConfigurationError("AWS_BEARER_TOKEN_BEDROCK is not configured")
    return LLM(
        model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        api_key=SecretStr(token),
        aws_region_name=os.getenv("AWS_REGION_NAME", DEFAULT_AWS_REGION),
        reasoning_effort=cast(Any, os.getenv("TCAD_REASONING_EFFORT", "medium")),
        stream=True,
    )

if TYPE_CHECKING:
    from openhands.sdk.conversation.state import ConversationState
    from openhands.sdk.event import ActionEvent


class WorkspaceTaskToolSet(TaskToolSet):
    """Native task delegation with child actions constrained to the workspace."""

    @classmethod
    def create(  # type: ignore[override]
        cls,
        conv_state: ConversationState,
        confirmation_handler: ConfirmationHandler | None = None,
    ) -> list[ToolDefinition[Any, Any]]:
        del confirmation_handler
        workspace = Path(conv_state.workspace.working_dir).resolve()

        def confirm_child_actions(
            _task_id: str, actions: list[ActionEvent]
        ) -> bool:
            return all(
                classify_action(workspace, action) is not SecurityRisk.HIGH
                for action in actions
            )

        return super().create(
            conv_state, confirmation_handler=confirm_child_actions
        )


register_tool(WorkspaceTaskToolSet.name, WorkspaceTaskToolSet)


@dataclass(frozen=True)
class OpenHandsRuntimeProfile:
    context: AgentContext
    tools: tuple[Tool, ...]
    domain_tools: DomainTools
    model: str
    reasoning_effort: str


def build_runtime(workspace: Path) -> OpenHandsRuntimeProfile:
    _, _, skills = load_skills_from_dir(workspace / "skills")
    context = AgentContext(skills=list(skills.values()))
    tools = get_default_tools(enable_browser=False, enable_sub_agents=False)
    tools.append(Tool(name=WorkspaceTaskToolSet.name))
    tools.append(Tool(name=TcadDomainTool.name))
    return OpenHandsRuntimeProfile(
        context=context,
        tools=tuple(tools),
        domain_tools=build_tools(workspace),
        model=os.getenv("LLM_MODEL", DEFAULT_LLM_MODEL),
        reasoning_effort=os.getenv("TCAD_REASONING_EFFORT", "medium"),
    )


class OpenHandsRuntimeFactory:
    """Create or reconstruct persistent local OpenHands conversations."""

    def __init__(self, runtime_root: Path, *, llm: LLM | None = None) -> None:
        self.runtime_root = runtime_root.resolve()
        self.llm = llm

    def create(
        self,
        workspace: Path,
        conversation_id: UUID,
        callback: Callable[[Event], None],
    ) -> RuntimeConversation:
        profile = build_runtime(workspace)
        register_builtins_agents(enable_browser=False)
        register_file_agents(PROJECT_ROOT)
        register_file_agents(workspace)
        llm = self.llm or llm_from_environment()
        agent = Agent(
            llm=llm,
            tools=list(profile.tools),
            agent_context=profile.context,
            condenser=get_default_condenser(
                llm.model_copy(update={"usage_id": "condenser"})
            ),
            tool_concurrency_limit=2,
        )
        persistence_dir = self.runtime_root / "openhands"
        persistence_dir.mkdir(parents=True, exist_ok=True)
        on_stream = getattr(callback, "on_stream", None)
        conversation = LocalConversation(
            agent=agent,
            workspace=workspace,
            persistence_dir=persistence_dir,
            conversation_id=conversation_id,
            callbacks=[callback],
            stream_callbacks=[on_stream] if on_stream is not None else None,
            max_iteration_per_run=80,
            visualizer=None,
            delete_on_close=False,
        )
        permission_grants = cast(
            set[PermissionCategory], getattr(callback, "permission_grants", set())
        )
        conversation.set_security_analyzer(
            WorkspaceSecurityAnalyzer(
                workspace=workspace.resolve(),
                grant_checker=permission_grants.__contains__,
            )
        )
        conversation.set_confirmation_policy(ConfirmRisky())
        return cast(RuntimeConversation, conversation)
