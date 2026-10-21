import json

from inspect_ai.model import ChatMessageTool, ChatMessageUser

from bench_core.agents.adapter import (
    CONTEXT_OPEN,
    AdapterMode,
    AgentAdapter,
    ToolResults,
    TurnEnd,
    split_assistant,
)
from bench_core.agents.fixtures import FixtureExecutor

from .agent_helpers import agent_version, answer, scripted, tool_call


def test_fixtures_look_up_match_omit_and_respond() -> None:
    agent = agent_version()
    fixtures = FixtureExecutor(agent.tools, agent.fixtures)
    claim = json.loads(fixtures.execute("get_claim", {"claim_id": "clm-test-5521 "}).content)
    assert claim["status"] == "declined"
    member = json.loads(fixtures.execute("get_member", {"member_id": "TEST-100231"}).content)
    assert "date_of_birth" not in member
    ok = {"member_id": "TEST-100231", "date_of_birth": "1984-03-12", "postcode": "2999"}
    assert json.loads(fixtures.execute("verify_identity", ok).content) == {"verified": True}
    wrong = {**ok, "date_of_birth": "1990-01-01"}
    assert json.loads(fixtures.execute("verify_identity", wrong).content)["verified"] is False
    missing = json.loads(fixtures.execute("get_claim", {"claim_id": "CLM-NOPE"}).content)
    assert "No record found" in missing["error"]
    escalation = fixtures.execute("create_escalation", {"reason": "x", "urgency": "routine"})
    assert json.loads(escalation.content)["reference"] == "ESC-TEST-0001"
    assert fixtures.execute("delete_everything", {}).error == "Unknown tool delete_everything."


def test_deployed_mode_keeps_our_prompt_and_delimits_context() -> None:
    adapter = AgentAdapter(agent_version(), scripted(), model_id="mockllm/model")
    system = adapter.system_message(context="Signed-in member: TEST-100231", caller_system="Hi")
    assert system is not None
    assert system.text.startswith(agent_version().prompt_text)
    assert CONTEXT_OPEN in system.text and "TEST-100231" in system.text
    assert [tool.name for tool in adapter.tools()][0] == "verify_identity"


def test_open_mode_passes_the_caller_prompt_through() -> None:
    adapter = AgentAdapter(
        agent_version(), scripted(), model_id="mockllm/model", mode=AdapterMode.open
    )
    system = adapter.system_message(caller_system="You are a pirate.")
    assert system is not None and system.text == "You are a pirate."
    assert adapter.tools() == []


async def test_fixture_tool_calls_are_answered_and_the_model_asked_again() -> None:
    model = scripted(
        tool_call("get_claim", claim_id="CLM-TEST-5521"),
        answer("Your claim was declined because outpatient imaging is not covered.", "Check claim"),
    )
    adapter = AgentAdapter(agent_version(), model, model_id="mockllm/model")
    turn = await adapter.respond([ChatMessageUser(content="Why was my MRI declined?")])
    assert turn.end is TurnEnd.answered
    assert [m.role for m in turn.messages] == ["assistant", "tool", "assistant"]
    tool_message = turn.messages[1]
    assert isinstance(tool_message, ChatMessageTool)
    assert json.loads(tool_message.text)["claim_id"] == "CLM-TEST-5521"
    assert turn.usage.input_tokens == 2400 and turn.usage.output_tokens == 300
    final = turn.final
    assert final is not None
    visible, thinking = split_assistant(final)
    assert visible.startswith("Your claim was declined")
    assert thinking == "Check claim"


async def test_simulated_tool_results_are_left_to_the_caller() -> None:
    adapter = AgentAdapter(
        agent_version(),
        scripted(tool_call("get_claim", claim_id="CLM-TEST-5521")),
        model_id="mockllm/model",
        tool_results=ToolResults.simulated,
    )
    turn = await adapter.respond([ChatMessageUser(content="Check my claim")])
    assert turn.end is TurnEnd.tool_calls_pending
    assert len(turn.messages) == 1


def test_config_hash_tracks_every_setting() -> None:
    base = AgentAdapter(agent_version(), scripted(), model_id="mockllm/model")
    other = AgentAdapter(agent_version(version="v1"), scripted(), model_id="mockllm/model")
    effort = AgentAdapter(
        agent_version(), scripted(), model_id="mockllm/model", generate={"reasoning_effort": "high"}
    )
    assert len({base.config_hash, other.config_hash, effort.config_hash}) == 3
