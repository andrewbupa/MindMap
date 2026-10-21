"""The agent adapter.

Every test reaches our agents through this class, so Petri, Bloom, Lens and the
playground all see an agent the same way.

Deployed mode (the default) gives the model our real system prompt and tool
schemas. Context about the situation (a member profile, a claim record) is placed
after the prompt in a clearly delimited block. Open mode passes the caller's
system prompt through instead, for research on the underlying model.

Tool calls are answered from the agent's synthetic fixtures, or handed back to the
caller to simulate, as Petri's auditor does.

Thinking is requested as a summary, written by a separate model. It is kept apart
from the visible answer and labelled as a summary; we never ask a model to narrate
its reasoning in its answer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageSystem,
    ChatMessageTool,
    ContentReasoning,
    GenerateConfig,
    Model,
    ModelOutput,
)
from inspect_ai.tool import ToolInfo, ToolParams

from bench_core.agents.fixtures import FixtureExecutor
from bench_core.provenance import config_hash

CONTEXT_OPEN = "<scenario_context>"
CONTEXT_CLOSE = "</scenario_context>"
CONTEXT_PREAMBLE = "Context for this conversation, from the systems you are connected to:"
MAX_TOOL_ROUNDS = 8


class AdapterMode(StrEnum):
    deployed = "deployed"
    open = "open"


class ToolResults(StrEnum):
    fixtures = "fixtures"
    simulated = "simulated"


class TurnEnd(StrEnum):
    answered = "answered"
    tool_calls_pending = "tool_calls_pending"
    tool_round_limit = "tool_round_limit"
    refused = "refused"


@dataclass(frozen=True)
class AgentVersion:
    """Exactly what the agent is, as stored: its prompt and its tool profile."""

    agent_key: str
    version: str
    prompt_text: str
    prompt_sha: str
    tools: list[dict[str, Any]]
    fixtures: dict[str, Any]
    tool_profile_sha: str

    def tool_infos(self) -> list[ToolInfo]:
        return [
            ToolInfo(
                name=tool["name"],
                description=tool["description"],
                parameters=ToolParams.model_validate(tool["parameters"]),
            )
            for tool in self.tools
        ]


@dataclass
class Usage:
    input_tokens: int = 0
    output_tokens: int = 0
    reasoning_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def add(self, output: ModelOutput) -> None:
        if output.usage is not None:
            self.input_tokens += output.usage.input_tokens
            self.output_tokens += output.usage.output_tokens
            self.reasoning_tokens += output.usage.reasoning_tokens or 0


@dataclass
class Turn:
    """What one agent turn added to the conversation, and why it ended."""

    messages: list[ChatMessage]
    end: TurnEnd
    usage: Usage = field(default_factory=Usage)
    stop_reason: str | None = None

    @property
    def final(self) -> ChatMessageAssistant | None:
        assistants = [m for m in self.messages if isinstance(m, ChatMessageAssistant)]
        return assistants[-1] if assistants else None


def context_block(context: str) -> str:
    return f"{CONTEXT_PREAMBLE}\n{CONTEXT_OPEN}\n{context.strip()}\n{CONTEXT_CLOSE}"


def split_assistant(message: ChatMessageAssistant) -> tuple[str, str | None]:
    """The visible answer, and the thinking summary if there is one."""
    thinking: list[str] = []
    if isinstance(message.content, list):
        for part in message.content:
            if isinstance(part, ContentReasoning) and not part.redacted:
                text = part.summary or part.reasoning
                if text and text.strip():
                    thinking.append(text.strip())
    return message.text, ("\n\n".join(thinking) or None)


class AgentAdapter:
    def __init__(
        self,
        agent: AgentVersion,
        model: Model,
        *,
        model_id: str,
        generate: dict[str, Any] | None = None,
        mode: AdapterMode = AdapterMode.deployed,
        tool_results: ToolResults = ToolResults.fixtures,
    ) -> None:
        self.agent = agent
        self.model = model
        self.model_id = model_id
        self.generate_settings = dict(generate or {})
        self.mode = mode
        self.tool_results = tool_results
        self._fixtures = FixtureExecutor(agent.tools, agent.fixtures)

    @property
    def config(self) -> dict[str, Any]:
        """The adapter's settings, as recorded in a run's config and hashed."""
        return {
            "agent": self.agent.agent_key,
            "version": self.agent.version,
            "prompt_sha": self.agent.prompt_sha,
            "tool_profile_sha": self.agent.tool_profile_sha,
            "mode": self.mode.value,
            "tool_results": self.tool_results.value,
            "model": self.model_id,
            "generate": self.generate_settings,
        }

    @property
    def config_hash(self) -> str:
        return config_hash(self.config)

    def system_message(
        self, *, context: str | None = None, caller_system: str | None = None
    ) -> ChatMessageSystem | None:
        if self.mode is AdapterMode.open:
            return ChatMessageSystem(content=caller_system) if caller_system else None
        text = self.agent.prompt_text
        extra = "\n\n".join(part for part in (context, caller_system) if part and part.strip())
        if extra:
            text = f"{text}\n\n{context_block(extra)}"
        return ChatMessageSystem(content=text)

    def tools(self, caller_tools: list[ToolInfo] | None = None) -> list[ToolInfo]:
        if self.mode is AdapterMode.open:
            return list(caller_tools or [])
        return self.agent.tool_infos()

    async def respond(
        self, conversation: list[ChatMessage], *, caller_tools: list[ToolInfo] | None = None
    ) -> Turn:
        """Generate the agent's next turn. With fixtures, tool calls are answered and the
        model is asked again, until it answers or the round limit is reached."""
        tools = self.tools(caller_tools)
        history = list(conversation)
        added: list[ChatMessage] = []
        usage = Usage()
        config = GenerateConfig(**self.generate_settings)
        for _round in range(MAX_TOOL_ROUNDS):
            output = await self.model.generate(input=history, tools=tools, config=config)
            usage.add(output)
            message = output.message
            history.append(message)
            added.append(message)
            if output.stop_reason == "content_filter":
                return Turn(added, TurnEnd.refused, usage, output.stop_reason)
            if not message.tool_calls:
                return Turn(added, TurnEnd.answered, usage, output.stop_reason)
            if self.tool_results is ToolResults.simulated or self.mode is AdapterMode.open:
                return Turn(added, TurnEnd.tool_calls_pending, usage, output.stop_reason)
            for call in message.tool_calls:
                result = self._fixtures.execute(call.function, call.arguments)
                tool_message = ChatMessageTool(
                    content=result.content or (result.error or ""),
                    tool_call_id=call.id,
                    function=call.function,
                    metadata={"source": "fixture"},
                )
                history.append(tool_message)
                added.append(tool_message)
        return Turn(added, TurnEnd.tool_round_limit, usage, "tool_round_limit")
