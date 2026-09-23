"""OpenHands production profile with progressive skills and no terminal tool."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from openhands.sdk import AgentContext, Tool
from openhands.sdk.skills import load_skills_from_dir

from tcad_agent.agent.tools import DomainTools, TcadDomainTool, build_tools


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
    return OpenHandsRuntimeProfile(
        context=context,
        tools=(Tool(name=TcadDomainTool.name),),
        domain_tools=build_tools(workspace),
        model=os.getenv("LLM_MODEL", "openai/gpt-5.6-terra"),
        reasoning_effort=os.getenv("TCAD_REASONING_EFFORT", "medium"),
    )

