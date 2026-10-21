"""Our agent as Petri's target.

Petri's auditor stages a system message and plays the member. In deployed mode the
target never sees the auditor's system text as its own prompt: it receives our
real prompt, with the auditor's text in the delimited context block after it, and
our real tool schemas. Every tool call is answered from the agent's synthetic
fixtures, so the auditor sees only what a member would: the agent's replies.

The control flow follows Petri's own ``target_agent`` and the TargetContext
protocol: ``expect()`` before every ``send_output``, messages mutated in place,
and fixture lookups wrapped in ``replayable`` so rollbacks replay identically.
"""

from __future__ import annotations

from inspect_ai.agent import Agent, AgentState, agent
from inspect_ai.model import ChatMessageSystem, ChatMessageTool, get_model
from inspect_ai.tool import ToolCall
from inspect_petri.target import TOOL_RESULT, ExitSignal, TargetContext

from bench_core.agents.adapter import MAX_TOOL_ROUNDS, AgentVersion, context_block
from bench_core.agents.fixtures import FixtureExecutor

LIMIT_MESSAGE = "Tool call limit reached for this turn. Answer with what you have."


@agent(name="bench_target")
def bench_target(version: AgentVersion) -> Agent:
    fixtures = FixtureExecutor(version.tools, version.fixtures)
    tools = version.tool_infos()

    async def execute(state: AgentState, context: TargetContext) -> AgentState:
        model = get_model(role="target")
        generate = context.replayable(model.generate, surface_errors=True)

        async def answer(calls: list[ToolCall], note: str | None = None) -> list[ChatMessageTool]:
            results = []
            for call in calls:
                result = fixtures.execute(call.function, call.arguments)
                results.append(
                    ChatMessageTool(
                        content=note or result.content or (result.error or ""),
                        tool_call_id=call.id,
                        function=call.function,
                        metadata={"source": "fixture"},
                    )
                )
            return results

        answer_calls = context.replayable(answer, deterministic=True)

        try:
            await context.wait_for_resume()
            staged = await context.system_message()
            user = await context.user_message()
            system = ChatMessageSystem(
                id=staged.id,
                content=f"{version.prompt_text}\n\n{context_block(staged.text)}",
                metadata={"bench": "deployed prompt with scenario context"},
            )
            state.messages[:] = [system, user]

            while True:
                for _round in range(MAX_TOOL_ROUNDS + 1):
                    state.output = await generate(input=state.messages, tools=tools)
                    state.messages.append(state.output.message)
                    calls = state.output.message.tool_calls or []
                    if not calls:
                        break
                    last = _round == MAX_TOOL_ROUNDS
                    state.messages.extend(
                        await answer_calls(calls, LIMIT_MESSAGE if last else None)
                    )
                    if last:
                        state.output = await generate(input=state.messages, tools=[])
                        state.messages.append(state.output.message)
                        break
                context.expect({TOOL_RESULT: set()})
                await context.send_output(state.output)
                state.messages.append(await context.user_message())
        except ExitSignal:
            return state

    return execute
