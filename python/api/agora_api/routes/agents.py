from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from agora_api.deps import Db, ReaderUser
from agora_api.schemas import (
    AgentDetail,
    AgentSummary,
    DiffRowOut,
    PersonaOut,
    PromptDiffOut,
    PromptVersionOut,
    PromptVersionText,
    ToolOut,
    ToolProfileOut,
)
from agora_core.agents.load import (
    AgentNotFound,
    current_personas,
    current_tool_profile,
    get_agent,
    load_agent_version,
)
from agora_core.diff import side_by_side
from agora_core.models import Agent, Persona, PromptVersion, ToolProfile
from agora_core.registry import version_sort_key

router = APIRouter(prefix="/agents", tags=["agents"])


def _not_found(error: AgentNotFound) -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, str(error))


async def _versions(db: Db, agent: Agent) -> list[PromptVersion]:
    rows = (
        await db.execute(select(PromptVersion).where(PromptVersion.agent_id == agent.id))
    ).scalars()
    return sorted(rows, key=lambda row: version_sort_key(row.version))


def _tool_profile(profile: ToolProfile) -> ToolProfileOut:
    return ToolProfileOut(
        id=profile.id,
        name=profile.name,
        sha256=profile.sha256,
        tools=[ToolOut.model_validate(tool) for tool in profile.tools],
        fixture_files=sorted(profile.fixtures),
        created_at=profile.created_at,
    )


@router.get("")
async def list_agents(_: ReaderUser, db: Db) -> list[AgentSummary]:
    agents = (await db.execute(select(Agent).order_by(Agent.name))).scalars().all()
    persona_counts = dict(
        (
            await db.execute(
                select(Persona.agent_id, func.count(func.distinct(Persona.key))).group_by(
                    Persona.agent_id
                )
            )
        ).all()
    )
    summaries = []
    for agent in agents:
        versions = [row.version for row in await _versions(db, agent)]
        if not versions:
            continue
        summaries.append(
            AgentSummary(
                key=agent.key,
                name=agent.name,
                owner=agent.owner,
                domains=agent.domains,
                description=agent.description,
                versions=versions,
                latest_version=versions[-1],
                persona_count=persona_counts.get(agent.id, 0),
            )
        )
    return summaries


@router.get("/{key}")
async def read_agent(key: str, _: ReaderUser, db: Db) -> AgentDetail:
    try:
        agent = await get_agent(db, key)
        profile = await current_tool_profile(db, agent)
    except AgentNotFound as error:
        raise _not_found(error) from error
    versions = await _versions(db, agent)
    personas = await current_personas(db, agent)
    return AgentDetail(
        key=agent.key,
        name=agent.name,
        owner=agent.owner,
        domains=agent.domains,
        description=agent.description,
        versions=[row.version for row in versions],
        latest_version=versions[-1].version if versions else "",
        persona_count=len(personas),
        prompt_versions=[PromptVersionOut.model_validate(row) for row in versions],
        tool_profile=_tool_profile(profile),
        personas=[PersonaOut.model_validate(row) for row in personas],
    )


@router.get("/{key}/versions/{version}")
async def read_version(key: str, version: str, _: ReaderUser, db: Db) -> PromptVersionText:
    try:
        stored = await load_agent_version(db, key, version)
    except AgentNotFound as error:
        raise _not_found(error) from error
    return PromptVersionText.model_validate(stored.prompt)


@router.get("/{key}/diff")
async def diff_versions(key: str, base: str, head: str, _: ReaderUser, db: Db) -> PromptDiffOut:
    try:
        left = await load_agent_version(db, key, base)
        right = await load_agent_version(db, key, head)
    except AgentNotFound as error:
        raise _not_found(error) from error
    rows = side_by_side(left.prompt.text, right.prompt.text)
    return PromptDiffOut(
        agent=key,
        base=PromptVersionOut.model_validate(left.prompt),
        head=PromptVersionOut.model_validate(right.prompt),
        rows=[DiffRowOut(**row.__dict__) for row in rows],
        added=sum(row.kind == "added" for row in rows),
        removed=sum(row.kind == "removed" for row in rows),
        changed=sum(row.kind == "changed" for row in rows),
    )
