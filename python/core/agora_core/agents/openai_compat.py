"""Translate between OpenAI chat completion requests and the adapter.

This lets any tool that expects a model (Bloom's rollout stage among them) target
an agent version at ``/api/v1/agents/{agent}/{version}/chat/completions``.

In deployed mode the caller's system messages do not replace our prompt: they
become the delimited context block after it. Sampling parameters such as
``temperature`` are ignored and reported back, since current models reject them
and the role's settings in config/models.yaml apply.
"""

from __future__ import annotations

import json
import time
import uuid
from typing import Any, Literal

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
)
from inspect_ai.tool import ToolCall, ToolInfo, ToolParams
from pydantic import BaseModel, ConfigDict

from agora_core.agents.adapter import AgentAdapter, Turn, TurnEnd, split_assistant


class CompatError(ValueError):
    pass


class ChatMessageIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    role: Literal["system", "developer", "user", "assistant", "tool"]
    content: str | list[dict[str, Any]] | None = None
    tool_calls: list[dict[str, Any]] | None = None
    tool_call_id: str | None = None
    name: str | None = None


class ChatCompletionIn(BaseModel):
    model_config = ConfigDict(extra="allow")

    model: str | None = None
    messages: list[ChatMessageIn]
    tools: list[dict[str, Any]] | None = None
    stream: bool = False
    agora_mode: Literal["deployed", "open"] = "deployed"
    agora_tool_results: Literal["fixtures", "simulated"] = "fixtures"

    @property
    def ignored(self) -> list[str]:
        """Fields a client sent that Agora does not use, such as temperature."""
        return sorted(self.model_extra or {})


def _text(content: str | list[dict[str, Any]] | None) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    return "".join(str(part.get("text", "")) for part in content if part.get("type") == "text")


def _arguments(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw or "{}")
    except json.JSONDecodeError as error:
        raise CompatError(f"tool call arguments are not valid JSON: {error}") from error
    if not isinstance(parsed, dict):
        raise CompatError("tool call arguments must be a JSON object")
    return parsed


def to_inspect(request: ChatCompletionIn) -> tuple[str | None, list[ChatMessage]]:
    """The caller's system text, and the rest of the conversation as Inspect messages."""
    system: list[str] = []
    messages: list[ChatMessage] = []
    names: dict[str, str] = {}
    for message in request.messages:
        text = _text(message.content)
        if message.role in ("system", "developer"):
            if text.strip():
                system.append(text.strip())
        elif message.role == "user":
            messages.append(ChatMessageUser(content=text))
        elif message.role == "assistant":
            calls = []
            for call in message.tool_calls or []:
                function = call.get("function") or {}
                calls.append(
                    ToolCall(
                        id=str(call.get("id") or uuid.uuid4()),
                        function=str(function.get("name", "")),
                        arguments=_arguments(function.get("arguments")),
                    )
                )
                names[calls[-1].id] = calls[-1].function
            messages.append(ChatMessageAssistant(content=text, tool_calls=calls or None))
        else:
            if not message.tool_call_id:
                raise CompatError("tool messages need a tool_call_id")
            messages.append(
                ChatMessageTool(
                    content=text,
                    tool_call_id=message.tool_call_id,
                    function=message.name or names.get(message.tool_call_id),
                )
            )
    if not messages:
        raise CompatError("send at least one user message")
    return ("\n\n".join(system) or None), messages


def caller_tools(request: ChatCompletionIn) -> list[ToolInfo]:
    tools = []
    for tool in request.tools or []:
        function = tool.get("function") or {}
        tools.append(
            ToolInfo(
                name=str(function.get("name", "")),
                description=str(function.get("description", "")),
                parameters=ToolParams.model_validate(
                    function.get("parameters") or {"type": "object", "properties": {}}
                ),
            )
        )
    return tools


FINISH_REASONS = {
    TurnEnd.answered: "stop",
    TurnEnd.tool_calls_pending: "tool_calls",
    TurnEnd.refused: "content_filter",
    TurnEnd.tool_round_limit: "length",
}


def _openai_tool_calls(message: ChatMessageAssistant) -> list[dict[str, Any]] | None:
    if not message.tool_calls:
        return None
    return [
        {
            "id": call.id,
            "type": "function",
            "function": {"name": call.function, "arguments": json.dumps(call.arguments)},
        }
        for call in message.tool_calls
    ]


def to_openai(
    turn: Turn, adapter: AgentAdapter, *, agent: str, version: str, ignored: list[str]
) -> dict[str, Any]:
    final = turn.final
    content, thinking = split_assistant(final) if final else ("", None)
    finish = FINISH_REASONS[turn.end]
    if turn.end is TurnEnd.answered and turn.stop_reason == "max_tokens":
        finish = "length"
    steps = [
        {"role": m.role, "content": m.text, "tool_calls": _openai_tool_calls(m)}
        if isinstance(m, ChatMessageAssistant)
        else {"role": m.role, "content": m.text, "tool_call_id": getattr(m, "tool_call_id", None)}
        for m in turn.messages[:-1]
    ]
    return {
        "id": f"chatcmpl-agora-{uuid.uuid4()}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": f"agora/{agent}/{version}",
        "system_fingerprint": adapter.agent.prompt_sha[:16],
        "choices": [
            {
                "index": 0,
                "message": {
                    "role": "assistant",
                    "content": content,
                    "tool_calls": _openai_tool_calls(final) if final else None,
                },
                "finish_reason": finish,
            }
        ],
        "usage": {
            "prompt_tokens": turn.usage.input_tokens,
            "completion_tokens": turn.usage.output_tokens,
            "total_tokens": turn.usage.total,
        },
        "agora": {
            "agent": agent,
            "version": version,
            "prompt_sha": adapter.agent.prompt_sha,
            "tool_profile_sha": adapter.agent.tool_profile_sha,
            "model": adapter.model_id,
            "mode": adapter.mode.value,
            "tool_results": adapter.tool_results.value,
            "config_hash": adapter.config_hash,
            "end": turn.end.value,
            "steps": steps,
            "thinking_summary": thinking,
            "ignored_parameters": ignored,
        },
    }
