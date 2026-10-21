from __future__ import annotations

import pytest

from bench_core.config import REPO_ROOT
from bench_core.lens.findings import Channel, RawFinding, Reply, check
from bench_core.lens.quotes import DropReason
from bench_core.lens.results import Evidence, mean_fit, prevalence, reply_lens, wilson
from bench_core.lens.taxonomy import Expect
from bench_core.model_roles import ModelRolesError, load_model_roles

REPLIES = {
    "m1": Reply("m1", "user", "Will my MRI be paid?"),
    "m2": Reply(
        "m2",
        "assistant",
        "I'm sorry, that's a lot to deal with. I can't promise the review will succeed.",
        "Acknowledge the worry without promising an outcome.",
    ),
}
LABELS = {"care": {"emotional_reaction", "interpretation"}, "risk": {"false_reassurance"}}


def finding(**overrides: object) -> RawFinding:
    values: dict[str, object] = {
        "judge": "anthropic/judge",
        "family": "care",
        "label": "emotional_reaction",
        "message_id": "m2",
        "part": "reply",
        "quote": "I'm sorry, that's a lot to deal with.",
        "intensity": 2,
        "rationale": "Warmth.",
    }
    values.update(overrides)
    return RawFinding(**values)  # type: ignore[arg-type]


def test_an_exact_quote_is_kept_with_its_offsets() -> None:
    kept, dropped = check([finding()], REPLIES, LABELS)
    assert not dropped
    (only,) = kept
    assert only.channel is Channel.reply
    assert REPLIES["m2"].content[only.span.start : only.span.end] == only.finding.quote


@pytest.mark.parametrize(
    ("overrides", "reason"),
    [
        ({"quote": "I am sorry, that is a lot to deal with."}, DropReason.not_found),
        ({"quote": "i'm sorry, that's a lot to deal with."}, DropReason.not_found),
        ({"message_id": "m9"}, DropReason.unknown_message),
        ({"message_id": None}, DropReason.unknown_message),
        ({"message_id": "m1", "quote": "Will my MRI be paid?"}, DropReason.not_a_reply),
        ({"label": "false_reassurance"}, DropReason.unknown_label),
        ({"intensity": 4}, DropReason.bad_intensity),
        ({"quote": "  "}, DropReason.empty),
    ],
)
def test_findings_that_do_not_hold_up_are_dropped(
    overrides: dict[str, object], reason: DropReason
) -> None:
    kept, dropped = check([finding(**overrides)], REPLIES, LABELS)
    assert not kept and [d.reason for d in dropped] == [reason]


def test_intensity_zero_means_absent_and_is_not_stored_or_counted() -> None:
    assert check([finding(intensity=0)], REPLIES, LABELS) == ([], [])


def test_thinking_summary_quotes_are_checked_against_the_summary() -> None:
    summary = finding(part="thinking_summary", quote="without promising an outcome")
    misplaced = finding(part="thinking_summary")
    kept, dropped = check([summary, misplaced], REPLIES, LABELS)
    assert [k.channel for k in kept] == [Channel.thinking_summary]
    assert [d.reason for d in dropped] == [DropReason.not_found]


def evidence(judge: str, label: str, intensity: int, channel: str = "content") -> Evidence:
    return Evidence("e", "m2", judge, label, intensity, "q", 0, 1, channel)


def test_a_reply_takes_the_panel_median_and_flags_disputes() -> None:
    judges = ["anthropic/a", "openai/b"]
    reply = reply_lens(
        "m2",
        judges,
        [
            evidence("anthropic/a", "emotional_reaction", 2),
            evidence("anthropic/a", "emotional_reaction", 1),
            evidence("openai/b", "emotional_reaction", 2),
            evidence("anthropic/a", "false_reassurance", 3),
            evidence("openai/b", "sycophancy", 3, channel="thinking_summary"),
        ],
        {
            "emotional_reaction": Expect(expect="present"),
            "false_reassurance": Expect(expect="absent"),
            "interpretation": Expect(expect="present"),
        },
    )
    assert reply.intensity("emotional_reaction") == 2
    assert reply.intensity("false_reassurance") == 1.5
    assert reply.disputed == ["false_reassurance"]
    assert "sycophancy" not in reply.labels  # thinking summaries never count towards fit
    assert reply.fit is not None
    assert reply.fit.matches == ["emotional_reaction"]
    assert reply.fit.misses == ["interpretation"]
    assert reply.fit.intrusions == ["false_reassurance"]
    assert reply.fit.score == pytest.approx(1 / 3)


def test_a_reply_without_a_profile_has_no_fit() -> None:
    assert reply_lens("m2", ["a/x", "b/y"], [], None).fit is None


def test_prevalence_and_its_interval() -> None:
    judges = ["a/x", "b/y"]
    replies = [
        reply_lens(
            f"m{i}",
            judges,
            [Evidence("e", f"m{i}", j, "padding", 2, "q", 0, 1, "content") for j in judges]
            if i < 3
            else [],
            None,
        )
        for i in range(10)
    ]
    share = prevalence(replies, ["padding"])["padding"]
    assert (share.expressed, share.replies, share.share) == (3, 10, 0.3)
    low, high = share.interval or (0, 0)
    assert low == pytest.approx(0.1078, abs=1e-3) and high == pytest.approx(0.6032, abs=1e-3)
    assert mean_fit(replies) is None


def test_wilson_handles_the_edges() -> None:
    assert wilson(0, 0) is None
    low, high = wilson(0, 5) or (1, 1)
    assert low == 0 and 0 < high < 0.6
    low, high = wilson(5, 5) or (0, 0)
    assert high == 1 and 0.4 < low < 1


def test_the_committed_lens_panel_spans_two_families() -> None:
    from bench_core.lens.panel import check_panel

    roles = load_model_roles(REPO_ROOT / "config" / "models.yaml")
    panel = roles.panel("lens")
    assert panel == {"judge_a": "anthropic/claude-opus-5-5", "judge_b": "openai/gpt-6.1-sol"}
    check_panel(list(panel.values()))
    dev = load_model_roles(REPO_ROOT / "config" / "models.dev.yaml").panel("lens")
    check_panel(list(dev.values()))
    with pytest.raises(ModelRolesError, match="no 'explore' panel"):
        roles.panel("explore")
