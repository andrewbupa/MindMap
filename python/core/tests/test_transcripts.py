from inspect_ai.model import ChatMessageAssistant, ChatMessageSystem, ChatMessageUser, ModelUsage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from bench_core.models import Message, Run, Transcript
from bench_core.storage import get_storage
from bench_core.transcripts import (
    append_messages,
    build_log,
    fetch_log,
    load_messages,
    log_key,
    store_log,
)
from testsupport.agents import answer


async def test_messages_round_trip_through_postgres_and_spaces(
    db: AsyncSession, s3_server: str
) -> None:
    run = Run(
        kind="playground",
        status="running",
        config={"k": 1},
        config_hash="0" * 64,
        git_commit="abc",
        model_ids={"target": "mockllm/model"},
        token_budget=1000,
    )
    db.add(run)
    await db.flush()
    transcript = Transcript(run_id=run.id, sample_index=0, log_uri="pending")
    db.add(transcript)
    await db.flush()
    reply = answer("Here is what your policy says.", thinking="Look at the policy first.")
    conversation = [
        ChatMessageSystem(content="You are the claims assistant."),
        ChatMessageUser(content="Am I covered?"),
        reply.message,
    ]
    rows = await append_messages(db, transcript, conversation)
    assert [row.index for row in rows] == [0, 1, 2]
    stored = (await db.execute(select(Message).where(Message.index == 2))).scalar_one()
    assert stored.content == "Here is what your policy says."
    assert stored.thinking_summary == "Look at the policy first."
    assert stored.thinking_full is None

    loaded = await load_messages(db, transcript.id)
    assert isinstance(loaded[2], ChatMessageAssistant)
    assert loaded[2].model_dump() == reply.message.model_dump()

    log = build_log(
        run=run,
        transcript=transcript,
        messages=loaded,
        model_id="mockllm/model",
        generate={"reasoning_effort": "medium"},
        usage=ModelUsage(input_tokens=10, output_tokens=5, total_tokens=15),
        task="bench/playground",
        metadata={"prompt_sha": "a" * 64, "agent": "claims-assistant"},
    )
    uri = await store_log(get_storage(), log, log_key(run.id, transcript.id))
    assert uri == f"s3://bench-test/runs/{run.id}/{transcript.id}.eval"

    fetched = await fetch_log(get_storage(), uri)
    assert fetched.eval.model == "mockllm/model"
    assert fetched.eval.metadata == {"prompt_sha": "a" * 64, "agent": "claims-assistant"}
    assert fetched.samples is not None
    assert [m.role for m in fetched.samples[0].messages] == ["system", "user", "assistant"]
    assert fetched.samples[0].messages[2].text == "Here is what your policy says."
