"""Builders for adapter tests: the real registry content and a scripted model."""

from __future__ import annotations

from typing import Any

from inspect_ai.model import (
    ChatMessageAssistant,
    ContentReasoning,
    ContentText,
    Model,
    ModelOutput,
    ModelUsage,
    get_model,
)

from bench_core.agents.adapter import AgentVersion
from bench_core.config import REPO_ROOT
from bench_core.registry import load_registry

USAGE = ModelUsage(input_tokens=1200, output_tokens=150, total_tokens=1350)


def agent_version(key: str = "claims-assistant", version: str = "v2") -> AgentVersion:
    loaded = load_registry(REPO_ROOT)[key]
    prompt = loaded.prompts[version]
    return AgentVersion(
        agent_key=key,
        version=version,
        prompt_text=prompt.text,
        prompt_sha=prompt.sha256,
        tools=loaded.tool_profile.tools_json(),
        fixtures=loaded.tool_profile.fixtures,
        tool_profile_sha=loaded.tool_profile.sha256,
    )


def answer(text: str, thinking: str | None = None) -> ModelOutput:
    parts: list[Any] = []
    if thinking:
        parts.append(ContentReasoning(reasoning=thinking, signature="sig-test"))
    parts.append(ContentText(text=text))
    output = ModelOutput.from_message(ChatMessageAssistant(content=parts, model="mockllm/model"))
    output.usage = USAGE
    return output


def tool_call(name: str, **arguments: Any) -> ModelOutput:
    output = ModelOutput.for_tool_call("mockllm/model", name, arguments)
    output.usage = USAGE
    return output


def scripted(*outputs: ModelOutput) -> Model:
    return get_model("mockllm/model", custom_outputs=list(outputs), memoize=False)


class RecordingModel:
    """A stand-in model that replays outputs and records what it was sent."""

    def __init__(self, *outputs: ModelOutput) -> None:
        self.outputs = list(outputs)
        self.calls: list[dict[str, Any]] = []

    async def generate(self, input: Any, tools: Any = None, config: Any = None) -> ModelOutput:
        self.calls.append({"input": list(input), "tools": list(tools or []), "config": config})
        if not self.outputs:
            raise AssertionError("the test model ran out of scripted outputs")
        return self.outputs.pop(0)
