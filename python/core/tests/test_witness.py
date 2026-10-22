from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from agora_core.config import REPO_ROOT
from agora_core.witness import (
    CONTRACT,
    CommandRunner,
    LexiconRunner,
    ReaderConfig,
    RunnerVersionError,
    SignalSpec,
    TokenSignal,
    TokenValue,
    WitnessError,
    WitnessMessage,
    WitnessRequest,
    WitnessResponse,
    check_response,
    compare,
    load_witness,
)

REPLY = "I can't promise cover. It might depend on the review."
PROBE = SignalSpec(
    name="reassurance", kind="probe", description="", label="false_reassurance", present_at=0.5
)
NOTES = SignalSpec(
    name="notes", kind="nla", description="", label="false_reassurance", present_at=0.5
)


def request(*signals: SignalSpec) -> WitnessRequest:
    return WitnessRequest(
        reader="test",
        model="open/model",
        version="v1",
        signals=list(signals or (PROBE, NOTES)),
        messages=[
            WitnessMessage(id="u", index=1, role="user", text="Will it be covered?"),
            WitnessMessage(id="a", index=2, role="assistant", text=REPLY),
        ],
        score=["a"],
    )


def signal(**changes: object) -> TokenSignal:
    base: dict[str, object] = {
        "message_id": "a",
        "name": "reassurance",
        "kind": "probe",
        "token_start": 0,
        "tokens": [TokenValue(start=0, end=1, value=0.2), TokenValue(start=2, end=7, value=0.8)],
    }
    return TokenSignal.model_validate({**base, **changes})


def response(*signals: TokenSignal, **changes: object) -> WitnessResponse:
    base: dict[str, object] = {
        "contract": CONTRACT,
        "runner_version": "v1",
        "tokens": 20,
        "signals": list(signals),
    }
    return WitnessResponse.model_validate({**base, **changes})


def test_committed_configs_load() -> None:
    assert load_witness(REPO_ROOT / "config" / "witness.yaml").readers == {}
    dev = load_witness(REPO_ROOT / "config" / "witness.dev.yaml")
    assert dev.reader("lexicon-dev").runner == "lexicon"
    with pytest.raises(WitnessError):
        dev.reader("missing")


@pytest.mark.parametrize(
    ("changes", "message"),
    [
        ({"runner": "command"}, "needs a command"),
        ({"command": ["run"]}, "runs no command"),
        ({"lexicon": {"other": ["word"]}}, "word list for each"),
        ({"signals": [PROBE.model_dump(), PROBE.model_dump()]}, "unique"),
    ],
)
def test_reader_config_is_checked(changes: dict[str, object], message: str) -> None:
    base = {
        "model": "agora/lexicon-dev",
        "runner": "lexicon",
        "version": "1",
        "signals": [PROBE.model_dump()],
        "lexicon": {"reassurance": ["promise"]},
    }
    with pytest.raises(ValueError, match=message):
        ReaderConfig.model_validate({**base, **changes})


def test_signals_that_do_not_hold_up_are_dropped_with_a_reason() -> None:
    good = signal()
    kept, dropped = check_response(
        response(
            good,
            signal(message_id="u"),
            signal(message_id="elsewhere"),
            signal(name="unasked"),
            signal(kind="persona_vector"),
            signal(tokens=[TokenValue(start=0, end=len(REPLY) + 1, value=0.1)]),
            signal(
                tokens=[
                    TokenValue(start=4, end=7, value=0.1),
                    TokenValue(start=2, end=5, value=0.1),
                ]
            ),
            signal(tokens=[TokenValue(start=3, end=3, value=0.1)]),
            signal(tokens=[TokenValue(start=0, end=1, value=float("nan"))]),
            signal(name="notes", kind="nla", explanation="  "),
        ),
        request(),
    )
    assert kept == [good]
    assert dropped == {
        "unknown_message": 2,
        "unknown_signal": 2,
        "bad_offsets": 3,
        "bad_value": 1,
        "no_explanation": 1,
    }


def test_a_runner_on_another_version_or_contract_is_refused() -> None:
    with pytest.raises(RunnerVersionError):
        check_response(response(runner_version="v2"), request())
    with pytest.raises(WitnessError, match="speaks"):
        check_response(response(contract="other/1"), request())


async def test_lexicon_runner_marks_words_with_exact_offsets() -> None:
    runner = LexiconRunner(lexicon={"reassurance": ["promise"], "notes": ["promise"]}, version="v1")
    result = await runner.read(request())
    kept, dropped = check_response(result, request())
    assert not dropped and len(kept) == 2
    probe = next(s for s in kept if s.kind == "probe")
    marked = [REPLY[t.start : t.end] for t in probe.tokens if t.value >= 0.5]
    assert marked == ["promise"]
    note = next(s for s in kept if s.kind == "nla")
    assert REPLY[note.char_start : note.char_end] == "I can't promise cover."
    assert note.token_start == 0 and "promise" in (note.explanation or "")
    # Every message is read for context, so the user's words count towards the budget.
    assert result.tokens == 5 + 14


def test_comparison_sorts_replies_into_four_cells() -> None:
    ethos = {"r1": {"false_reassurance": 2.0}, "r2": {"false_reassurance": 1.0}, "r3": {}}
    peaks = {"r1": {"reassurance": 0.9}, "r3": {"reassurance": 0.7}, "r4": {"reassurance": 0.1}}
    unlabelled = SignalSpec(name="loose", kind="probe", description="")
    (result,) = compare(["r1", "r2", "r3", "r4"], ethos, peaks, [PROBE, unlabelled], 1.0)
    assert (result.both, result.ethos_only, result.witness_only, result.neither) == (
        ["r1"],
        ["r2"],
        ["r3"],
        ["r4"],
    )
    assert result.agreement == 0.5
    assert result.positive == pytest.approx(1 / 3)


RUNNER = """
import json, sys
request = json.load(sys.stdin)
mode = sys.argv[1]
if mode == "fail":
    print("no GPU here", file=sys.stderr)
    sys.exit(3)
if mode == "garbage":
    print("not json")
    sys.exit(0)
if mode == "slow":
    import time
    time.sleep(5)
reply = next(m for m in request["messages"] if m["id"] in request["score"])
print(json.dumps({
    "contract": request["contract"],
    "runner_version": request["version"],
    "tokens": 7,
    "signals": [{
        "message_id": reply["id"], "name": request["signals"][0]["name"], "kind": "probe",
        "token_start": 0, "tokens": [{"start": 0, "end": 1, "value": 0.25}],
    }],
}))
"""


@pytest.fixture
def runner_script(tmp_path: Path) -> Path:
    path = tmp_path / "runner.py"
    path.write_text(RUNNER)
    return path


async def test_command_runner_speaks_the_contract(runner_script: Path) -> None:
    runner = CommandRunner(command=[sys.executable, str(runner_script), "ok"], timeout_seconds=30)
    result = await runner.read(request())
    kept, _ = check_response(result, request())
    assert result.tokens == 7 and [s.tokens[0].value for s in kept] == [0.25]


@pytest.mark.parametrize(
    ("mode", "message"),
    [
        ("fail", "exited with code 3: no GPU here"),
        ("garbage", "does not follow"),
        ("slow", "longer than 1 seconds"),
    ],
)
async def test_command_runner_failures_are_explained(
    runner_script: Path, mode: str, message: str
) -> None:
    runner = CommandRunner(command=[sys.executable, str(runner_script), mode], timeout_seconds=1)
    with pytest.raises(WitnessError, match=message):
        await runner.read(request())


def test_the_request_is_plain_json() -> None:
    sent = json.loads(request().model_dump_json())
    assert sent["contract"] == CONTRACT and sent["score"] == ["a"]
    assert [m["role"] for m in sent["messages"]] == ["user", "assistant"]
