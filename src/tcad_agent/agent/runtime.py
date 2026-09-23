"""OpenHands production profile for the local repository agent."""

from __future__ import annotations

import os
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID

from openhands.sdk import LLM, Agent, AgentContext, Conversation, Tool
from openhands.sdk.conversation.impl.local_conversation import LocalConversation
from openhands.sdk.event import Event
from openhands.sdk.security import ConfirmRisky
from openhands.sdk.skills import load_skills_from_dir
from openhands.sdk.subagent import register_file_agents
from openhands.tools.preset.default import (
    get_default_condenser,
    get_default_tools,
    register_builtins_agents,
)

from tcad_agent.agent.policy import WorkspaceSecurityAnalyzer
from tcad_agent.agent.tools import DomainTools, TcadDomainTool, build_tools

DEFAULT_LLM_MODEL = "bedrock/global.anthropic.claude-sonnet-4-6"


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
    tools = get_default_tools(enable_browser=False, enable_sub_agents=True)
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

    def __init__(self, runtime_root: Path) -> None:
        self.runtime_root = runtime_root.resolve()

    def create(
        self,
        workspace: Path,
        conversation_id: UUID,
        callback: Callable[[Event], None],
    ) -> LocalConversation:
        profile = build_runtime(workspace)
        register_builtins_agents(enable_browser=False)
        register_file_agents(workspace)
        llm = LLM(
            model=profile.model,
            aws_region_name=os.getenv("AWS_REGION_NAME", "us-east-1"),
            reasoning_effort=cast(Any, profile.reasoning_effort),
        )
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
        conversation = cast(
            LocalConversation,
            Conversation(
                agent=agent,
                workspace=workspace,
                persistence_dir=persistence_dir,
                conversation_id=conversation_id,
                callbacks=[callback],
                max_iteration_per_run=80,
                visualizer=None,
                delete_on_close=False,
            ),
        )
        conversation.set_security_analyzer(
            WorkspaceSecurityAnalyzer(workspace=workspace.resolve())
        )
        conversation.set_confirmation_policy(ConfirmRisky())
        return conversation
