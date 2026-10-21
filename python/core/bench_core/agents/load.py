"""Load an agent version from Postgres: the exact prompt and tool profile a run will record."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.agents.adapter import AgentVersion
from bench_core.models import Agent, Persona, PromptVersion, ToolProfile


class AgentNotFound(LookupError):
    pass


@dataclass(frozen=True)
class StoredAgentVersion:
    agent: Agent
    prompt: PromptVersion
    tool_profile: ToolProfile

    def adapter_input(self) -> AgentVersion:
        return AgentVersion(
            agent_key=self.agent.key,
            version=self.prompt.version,
            prompt_text=self.prompt.text,
            prompt_sha=self.prompt.sha256,
            tools=self.tool_profile.tools,
            fixtures=self.tool_profile.fixtures,
            tool_profile_sha=self.tool_profile.sha256,
        )


async def get_agent(db: AsyncSession, key: str) -> Agent:
    agent = (await db.execute(select(Agent).where(Agent.key == key))).scalar_one_or_none()
    if agent is None:
        raise AgentNotFound(f"No agent called {key}.")
    return agent


async def current_tool_profile(db: AsyncSession, agent: Agent) -> ToolProfile:
    profile = (
        await db.execute(
            select(ToolProfile)
            .where(ToolProfile.agent_id == agent.id)
            .order_by(ToolProfile.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()
    if profile is None:
        raise AgentNotFound(f"{agent.key} has no tool profile.")
    return profile


async def current_personas(db: AsyncSession, agent: Agent) -> list[Persona]:
    """The newest row for each persona key."""
    rows = (
        await db.execute(
            select(Persona)
            .where(Persona.agent_id == agent.id)
            .ext(distinct_on(Persona.key))
            .order_by(Persona.key, Persona.created_at.desc())
        )
    ).scalars()
    return list(rows)


async def load_agent_version(db: AsyncSession, key: str, version: str) -> StoredAgentVersion:
    agent = await get_agent(db, key)
    prompt = (
        await db.execute(
            select(PromptVersion).where(
                PromptVersion.agent_id == agent.id, PromptVersion.version == version
            )
        )
    ).scalar_one_or_none()
    if prompt is None:
        raise AgentNotFound(f"{key} has no prompt version {version}.")
    return StoredAgentVersion(agent, prompt, await current_tool_profile(db, agent))
