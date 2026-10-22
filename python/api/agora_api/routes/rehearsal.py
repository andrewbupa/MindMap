"""The rehearsal: chat with any agent version, and keep the conversation as a run."""

from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from agora_api.deps import AppSettings, AuthorUser, Db, ReaderUser
from agora_api.models_dep import Models, Roles
from agora_api.schemas import (
    MessageOut,
    PersonaOut,
    RehearsalOut,
    RehearsalSay,
    RehearsalStart,
    RehearsalTurnOut,
    RunOut,
)
from agora_core import rehearsal
from agora_core.agents.adapter import AdapterMode, AgentAdapter
from agora_core.agents.load import AgentNotFound, current_personas, load_agent_version
from agora_core.models import Message, Persona, Role, Run, RunKind, RunStatus, User
from agora_core.provenance import ProvenanceError, current_git_commit
from agora_core.storage import get_storage

router = APIRouter(prefix="/rehearsal", tags=["rehearsal"])


async def _run(db: Db, run_id: uuid.UUID, *, lock: bool = False) -> Run:
    query = select(Run).where(Run.id == run_id, Run.kind == RunKind.rehearsal.value)
    if lock:
        query = query.with_for_update()
    run = (await db.execute(query)).scalar_one_or_none()
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such rehearsal conversation.")
    return run


def _require_owner(run: Run, user: User) -> None:
    if run.launched_by != user.id and not user.has_role(Role.admin):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN, "Only the person who started this can add to it."
        )


async def _adapter(db: Db, run: Run, models: Models, roles: Roles) -> AgentAdapter:
    config = run.config
    stored = await load_agent_version(db, config["agent"], config["version"])
    if stored.tool_profile.sha256 != config["tool_profile_sha"]:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "The agent's tools changed since this conversation began. Start a new one.",
        )
    return AgentAdapter(
        stored.adapter_input(),
        models(config["model"]),
        model_id=config["model"],
        generate=config["generate"],
        mode=AdapterMode(config["mode"]),
    )


async def _persona(db: Db, run: Run) -> Persona | None:
    key = run.config.get("persona")
    if not key or run.agent_id is None:
        return None
    return (
        await db.execute(
            select(Persona)
            .where(Persona.agent_id == run.agent_id, Persona.key == key)
            .order_by(Persona.created_at.desc())
            .limit(1)
        )
    ).scalar_one_or_none()


async def _out(db: Db, run: Run) -> RehearsalOut:
    transcript = await rehearsal.transcript_for(db, run)
    messages = (
        await db.execute(
            select(Message).where(Message.transcript_id == transcript.id).order_by(Message.index)
        )
    ).scalars()
    persona = await _persona(db, run)
    return RehearsalOut(
        run=RunOut.model_validate(run),
        agent=run.config["agent"],
        version=run.config["version"],
        persona=PersonaOut.model_validate(persona) if persona else None,
        messages=[MessageOut.model_validate(message) for message in messages],
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def start_conversation(
    body: RehearsalStart,
    user: AuthorUser,
    db: Db,
    settings: AppSettings,
    models: Models,
    roles: Roles,
) -> RehearsalOut:
    try:
        stored = await load_agent_version(db, body.agent, body.version)
    except AgentNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    if body.persona and body.persona not in {
        p.key for p in await current_personas(db, stored.agent)
    }:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND, f"{body.agent} has no persona {body.persona}."
        )
    target = roles.role("target")
    mode = AdapterMode(body.mode)
    adapter = AgentAdapter(
        stored.adapter_input(),
        models(target.model),
        model_id=target.model,
        generate=target.generate,
        mode=mode,
    )
    try:
        run = await rehearsal.start(
            db,
            stored=stored,
            adapter=adapter,
            roles=roles,
            git_commit=current_git_commit(settings.repo_root, settings.git_commit),
            launched_by=user.id,
            persona_key=body.persona,
            context=body.context if mode is AdapterMode.deployed else None,
            caller_system=body.system_prompt if mode is AdapterMode.open else None,
        )
    except ProvenanceError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, f"Cannot record this run: {error}") from error
    await db.commit()
    return await _out(db, run)


@router.get("/{run_id}")
async def read_conversation(run_id: uuid.UUID, _: ReaderUser, db: Db) -> RehearsalOut:
    return await _out(db, await _run(db, run_id))


@router.post("/{run_id}/messages")
async def say(
    run_id: uuid.UUID,
    body: RehearsalSay,
    user: AuthorUser,
    db: Db,
    models: Models,
    roles: Roles,
) -> RehearsalTurnOut:
    run = await _run(db, run_id, lock=True)
    _require_owner(run, user)
    adapter = await _adapter(db, run, models, roles)
    try:
        result = await rehearsal.take_turn(db, run, adapter, roles, body.content)
    except rehearsal.RehearsalError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    if result.stopped_at_budget:
        await rehearsal.finish(
            db, run, get_storage(), actor_id=None, status=RunStatus.stopped_at_budget
        )
    await db.commit()
    return RehearsalTurnOut(
        run=RunOut.model_validate(run),
        messages=[MessageOut.model_validate(message) for message in result.messages],
        stopped_at_budget=result.stopped_at_budget,
    )


@router.post("/{run_id}/finish")
async def finish_conversation(run_id: uuid.UUID, user: AuthorUser, db: Db) -> RehearsalOut:
    run = await _run(db, run_id, lock=True)
    _require_owner(run, user)
    try:
        await rehearsal.finish(db, run, get_storage(), actor_id=user.id)
    except rehearsal.RehearsalError as error:
        raise HTTPException(status.HTTP_409_CONFLICT, str(error)) from error
    await db.commit()
    return await _out(db, run)


@router.get("")
async def list_conversations(user: ReaderUser, db: Db, mine: bool = True) -> list[RunOut]:
    query = (
        select(Run)
        .where(Run.kind == RunKind.rehearsal.value)
        .order_by(Run.created_at.desc())
        .limit(50)
    )
    if mine:
        query = query.where(Run.launched_by == user.id)
    return [RunOut.model_validate(run) for run in (await db.execute(query)).scalars()]
