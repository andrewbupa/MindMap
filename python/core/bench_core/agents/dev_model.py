"""A deterministic development model, ``benchdev/scripted``, for running Bench without
provider keys: local development, demos and browser checks. Never used in production;
config/models.yaml names real models, and only infra/dev/models.yaml names this one.

It looks up any claim number or member number it sees with the agent's tools, then
answers plainly, with a short thinking summary, so every part of the adapter runs.
"""

from __future__ import annotations

import json
import re
import uuid
from typing import Any

from inspect_ai.model import (
    ChatMessage,
    ChatMessageAssistant,
    ChatMessageTool,
    ChatMessageUser,
    ContentReasoning,
    ContentText,
    GenerateConfig,
    ModelAPI,
    ModelOutput,
    ModelUsage,
    modelapi,
)
from inspect_ai.tool import ToolCall, ToolChoice, ToolInfo

CLAIM = re.compile(r"\bCLM-TEST-\d+\b", re.IGNORECASE)
MEMBER = re.compile(r"\bTEST-\d{6}\b", re.IGNORECASE)


def _usage(input: list[ChatMessage], text: str) -> ModelUsage:
    words_in = sum(len(message.text.split()) for message in input)
    words_out = len(text.split())
    return ModelUsage(
        input_tokens=words_in * 4 // 3,
        output_tokens=words_out * 4 // 3 + 20,
        total_tokens=(words_in + words_out) * 4 // 3 + 20,
    )


@modelapi(name="benchdev")
def benchdev() -> type[ModelAPI]:
    return ScriptedDevModel


class ScriptedDevModel(ModelAPI):
    def __init__(
        self,
        model_name: str,
        base_url: str | None = None,
        api_key: str | None = None,
        config: GenerateConfig = GenerateConfig(),  # noqa: B008
        **model_args: Any,
    ) -> None:
        super().__init__(model_name, base_url, api_key, [], config)

    async def generate(
        self,
        input: list[ChatMessage],
        tools: list[ToolInfo],
        tool_choice: ToolChoice,
        config: GenerateConfig,
    ) -> ModelOutput:
        model = f"benchdev/{self.model_name}"
        names = {tool.name for tool in tools}
        last_user = next((m for m in reversed(input) if isinstance(m, ChatMessageUser)), None)
        answered = isinstance(input[-1], ChatMessageTool) if input else False
        said = last_user.text if last_user else ""

        if not answered and last_user is not None:
            call = None
            if (claim := CLAIM.search(said)) and "get_claim" in names:
                call = ToolCall(
                    id=str(uuid.uuid4()),
                    function="get_claim",
                    arguments={"claim_id": claim.group(0).upper()},
                )
            elif (member := MEMBER.search(said)) and "get_policy_cover" in names:
                call = ToolCall(
                    id=str(uuid.uuid4()),
                    function="get_policy_cover",
                    arguments={"member_id": member.group(0).upper()},
                )
            if call is not None:
                message = ChatMessageAssistant(content="", tool_calls=[call], model=model)
                output = ModelOutput.from_message(message, stop_reason="tool_calls")
                output.usage = _usage(input, "")
                return output

        if answered:
            found = input[-1].text
            try:
                record = json.loads(found)
                detail = ", ".join(f"{k}: {v}" for k, v in record.items() if isinstance(v, str))
            except (json.JSONDecodeError, AttributeError):
                detail = found
            text = f"Here is what I found. {detail}"
            thinking = "Summarise the tool result plainly and do not promise an outcome."
        else:
            text = (
                "This is Bench's development model, not a real agent. "
                f"You said: {said.strip()[:300]}"
            )
            thinking = "No tool applies; acknowledge the message."
        message = ChatMessageAssistant(
            content=[ContentReasoning(reasoning=thinking), ContentText(text=text)], model=model
        )
        output = ModelOutput.from_message(message)
        output.usage = _usage(input, text)
        return output
