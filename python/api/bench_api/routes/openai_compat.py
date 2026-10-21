"""The adapter as an OpenAI-compatible chat completions endpoint, for machine clients.

Clients authenticate with an API token from Settings, sent as a bearer token.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException, status
from sqlalchemy import select

from bench_api.deps import Db
from bench_api.models_dep import Models, Roles
from bench_api.sessions import hash_token
from bench_core.agents.adapter import AdapterMode, AgentAdapter, ToolResults
from bench_core.agents.load import AgentNotFound, load_agent_version
from bench_core.agents.openai_compat import (
    ChatCompletionIn,
    CompatError,
    caller_tools,
    to_inspect,
    to_openai,
)
from bench_core.models import ApiToken

router = APIRouter(prefix="/v1/agents", tags=["openai-compatible"])

TOUCH_INTERVAL = timedelta(minutes=1)


async def api_token(db: Db, authorization: Annotated[str | None, Header()] = None) -> ApiToken:
    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "Send an API token as 'Authorization: Bearer <token>'.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    row = (
        await db.execute(select(ApiToken).where(ApiToken.token_hash == hash_token(token.strip())))
    ).scalar_one_or_none()
    if row is None or row.revoked_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "This API token is not valid.")
    now = datetime.now(UTC)
    if row.last_used_at is None or now - row.last_used_at > TOUCH_INTERVAL:
        row.last_used_at = now
        await db.commit()
    return row


Token = Annotated[ApiToken, Depends(api_token)]


@router.post("/{agent}/{version}/chat/completions")
async def chat_completions(
    agent: str,
    version: str,
    body: ChatCompletionIn,
    _: Token,
    db: Db,
    models: Models,
    roles: Roles,
) -> dict[str, Any]:
    if body.stream:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Streaming is not supported.")
    try:
        stored = await load_agent_version(db, agent, version)
    except AgentNotFound as error:
        raise HTTPException(status.HTTP_404_NOT_FOUND, str(error)) from error
    target = roles.role("target")
    adapter = AgentAdapter(
        stored.adapter_input(),
        models(target.model),
        model_id=target.model,
        generate=target.generate,
        mode=AdapterMode(body.bench_mode),
        tool_results=ToolResults(body.bench_tool_results),
    )
    try:
        caller_system, conversation = to_inspect(body)
    except CompatError as error:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(error)) from error
    system = adapter.system_message(caller_system=caller_system)
    turn = await adapter.respond(
        [system, *conversation] if system else conversation, caller_tools=caller_tools(body)
    )
    return to_openai(turn, adapter, agent=agent, version=version, ignored=body.ignored)
