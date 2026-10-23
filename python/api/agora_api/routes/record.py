"""Reports: exports of a run with its full provenance. Every export is audited."""

from __future__ import annotations

import csv
import io
import json
import uuid

from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from sqlalchemy import select

from agora_api.deps import AppSettings, Db, ReaderUser
from agora_api.report_pdf import Section, comparison_report, run_report
from agora_api.routes.ethos import build_comparison
from agora_api.routes.runs import started_month
from agora_api.schemas import EthosCompareOut, IntervalOut, LabelPrevalenceOut, RunOut
from agora_core import audit
from agora_core.ethos.read import load_run_ethos
from agora_core.ethos.taxonomy import load_ethos
from agora_core.models import Run, RunKind, Scenario, ScenarioSet, Score, Transcript, User
from agora_core.seeds import dimension_names

router = APIRouter(prefix="/record", tags=["record"])

PROVENANCE = (
    "run_id",
    "run_kind",
    "run_status",
    "git_commit",
    "config_hash",
    "prompt_sha",
    "seed_hash",
    "taxonomy_version",
    "model_ids",
    "engine_versions",
)


def provenance(run: Run) -> dict[str, str]:
    return {
        "run_id": str(run.id),
        "run_kind": run.kind,
        "run_status": run.status,
        "git_commit": run.git_commit,
        "config_hash": run.config_hash,
        "prompt_sha": run.prompt_sha or "",
        "seed_hash": run.seed_hash or "",
        "taxonomy_version": run.taxonomy_version or "",
        "model_ids": json.dumps(run.model_ids, sort_keys=True),
        "engine_versions": json.dumps(run.engine_versions, sort_keys=True),
    }


@router.get("/runs/{run_id}/scores.csv", response_class=Response)
async def export_scores(run_id: uuid.UUID, user: ReaderUser, db: Db) -> Response:
    """One row per transcript and dimension, each carrying the run's provenance.
    Scores from transcripts with content notes are included; their text is not."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    rows = (
        await db.execute(
            select(Transcript, Score, Scenario)
            .join(Score, Score.transcript_id == Transcript.id)
            .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
            .where(Transcript.run_id == run.id)
            .order_by(Transcript.sample_index, Transcript.epoch, Score.dimension)
        )
    ).all()
    buffer = io.StringIO()
    fields = [
        "transcript_id",
        "scenario",
        "epoch",
        "dimension",
        "value",
        "scale_max",
        "judge_model",
        "log_uri",
        *PROVENANCE,
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    shared = provenance(run)
    for transcript, score, scenario in rows:
        writer.writerow(
            {
                "transcript_id": str(transcript.id),
                "scenario": scenario.key if scenario else "",
                "epoch": transcript.epoch,
                "dimension": score.dimension,
                "value": score.value,
                "scale_max": score.scale_max,
                "judge_model": score.judge_model or "",
                "log_uri": transcript.log_uri or "",
                **shared,
            }
        )
    await audit.record(
        db,
        "report.export",
        actor_id=user.id,
        target_type="run",
        target_id=run.id,
        detail={"format": "csv", "rows": len(rows)},
    )
    await db.commit()
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="agora-{run.kind}-{run.id}.csv"'},
    )


@router.get("/runs/{run_id}/provenance")
async def run_provenance(run_id: uuid.UUID, user: ReaderUser, db: Db) -> dict[str, object]:
    """Everything needed to reproduce the run, including its full config."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    await audit.record(
        db, "report.provenance", actor_id=user.id, target_type="run", target_id=run.id
    )
    await db.commit()
    return {**provenance(run), "config": run.config, "title": run.title}


@router.get("/runs")
async def list_report_runs(
    _: ReaderUser,
    db: Db,
    settings: AppSettings,
    month: str | None = Query(default=None, pattern=r"^\d{4}-(0[1-9]|1[0-2])$"),
    limit: int = Query(default=100, ge=1, le=1000),
) -> list[RunOut]:
    """Recent runs of every kind, for export; with a month, the runs started in it."""
    query = select(Run).order_by(Run.created_at.desc()).limit(limit)
    if month:
        query = query.where(started_month(settings.time_zone) == month)
    runs = (await db.execute(query)).scalars()
    return [RunOut.model_validate(run) for run in runs]


async def _audited(db: Db, user: User, run: Run, fmt: str, rows: int) -> None:
    await audit.record(
        db,
        "report.export",
        actor_id=user.id,
        target_type="run",
        target_id=run.id,
        detail={"format": fmt, "rows": rows},
    )
    await db.commit()


@router.get("/runs/{run_id}/findings.csv", response_class=Response)
async def export_findings(
    run_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> Response:
    """One row per Ethos finding, with the run's provenance. Quotes from transcripts with
    content notes are left blank."""
    run = await db.get(Run, run_id)
    if run is None or run.kind != RunKind.ethos.value:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such Ethos run.")
    order = [label.key for label in load_ethos(settings.repo_root).taxonomy.labels]
    ethos = await load_run_ethos(db, run, order=order)
    families = {label.key: label.family for label in ethos.labels}
    buffer = io.StringIO()
    fields = [
        "transcript_id",
        "scenario",
        "message_id",
        "label",
        "family",
        "judge_model",
        "intensity",
        "channel",
        "char_start",
        "char_end",
        "quote",
        *PROVENANCE,
    ]
    writer = csv.DictWriter(buffer, fieldnames=fields)
    writer.writeheader()
    shared = provenance(run)
    count = 0
    for transcript in ethos.transcripts:
        noted = bool(transcript.scenario and transcript.scenario.content_notes)
        for item in transcript.evidence:
            count += 1
            writer.writerow(
                {
                    "transcript_id": str(transcript.transcript.id),
                    "scenario": transcript.scenario.key if transcript.scenario else "",
                    "message_id": item.message_id,
                    "label": item.label,
                    "family": families.get(item.label, ""),
                    "judge_model": item.judge,
                    "intensity": item.intensity,
                    "channel": item.channel,
                    "char_start": item.start,
                    "char_end": item.end,
                    "quote": "" if noted else item.quote,
                    **shared,
                }
            )
    await _audited(db, user, run, "csv-findings", count)
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="agora-ethos-{run.id}-findings.csv"'
        },
    )


def _percent(value: float | None) -> str:
    return "not scored" if value is None else f"{round(value * 100)}%"


async def _sections(db: Db, run: Run, settings: AppSettings, user: User) -> list[Section]:
    if run.kind == RunKind.inquiry.value:
        ours = dimension_names(settings.repo_root)
        rows = (
            await db.execute(
                select(Transcript, Scenario)
                .outerjoin(Scenario, Scenario.id == Transcript.scenario_id)
                .where(Transcript.run_id == run.id)
                .order_by(Transcript.sample_index, Transcript.epoch)
            )
        ).all()
        scores: dict[uuid.UUID, dict[str, float]] = {t.id: {} for t, _ in rows}
        if scores:
            for score in (
                await db.execute(select(Score).where(Score.transcript_id.in_(list(scores))))
            ).scalars():
                scores[score.transcript_id][score.dimension] = score.value
        return [
            Section(
                heading="Scores on our dimensions",
                intro="Judge scores from 1 to 10 on Agora's own dimensions. Petri's built-in"
                " dimensions are in the CSV export.",
                header=["Scenario", "Repetition", "Scores", "Judge's summary"],
                rows=[
                    [
                        scenario.key if scenario else "",
                        str(t.epoch),
                        ", ".join(
                            f"{d.replace('_', ' ')} {scores[t.id][d]:g}"
                            for d in ours
                            if d in scores[t.id]
                        ),
                        "" if scenario and scenario.content_notes else (t.summary or ""),
                    ]
                    for t, scenario in rows
                ],
            )
        ]
    if run.kind == RunKind.tally.value:
        from agora_api.routes.tally import tally_rates, tally_rollouts

        rollouts = (await tally_rollouts(db, [run]))[run.id]
        rates = tally_rates(run, rollouts)
        overall = rates.overall
        spread = rates.spread
        return [
            Section(
                heading="Elicitation rate",
                intro=(
                    f"{_percent(overall.rate)} of scored rollouts reached presence"
                    f" {rates.threshold:g} or more ({overall.elicited} of {overall.rollouts}),"
                    f" on behaviour {run.config['behaviour']}. Repetitions ranged from"
                    f" {_percent(spread[0]) if spread else 'none'} to"
                    f" {_percent(spread[1]) if spread else 'none'}."
                    f" {overall.unscored} rollouts were not scored. Cite this rate with the"
                    " seed hash above."
                ),
                header=["Repetition", "Rate", "Scored 7 or more", "Mean presence"],
                rows=[
                    [
                        str(epoch),
                        _percent(t.rate),
                        f"{t.elicited} of {t.rollouts}",
                        "" if t.mean_score is None else f"{t.mean_score:.1f}",
                    ]
                    for epoch, t in rates.by_epoch.items()
                ],
            ),
            Section(
                heading="By scenario",
                header=["Scenario", "Rate", "Scored 7 or more", "Mean presence"],
                rows=[
                    [
                        key.replace("_", " "),
                        _percent(t.rate),
                        f"{t.elicited} of {t.rollouts}",
                        "" if t.mean_score is None else f"{t.mean_score:.1f}",
                    ]
                    for key, t in rates.by_scenario.items()
                ],
            ),
        ]
    if run.kind == RunKind.ethos.value:
        from agora_api.routes.ethos import label_shares

        order = [label.key for label in load_ethos(settings.repo_root).taxonomy.labels]
        ethos = await load_run_ethos(db, run, order=order)
        shares = label_shares(ethos.replies, ethos.labels)
        kept: dict[str, int] = {}
        for t in ethos.transcripts:
            for item in t.evidence:
                kept[item.judge] = kept.get(item.judge, 0) + 1
        return [
            Section(
                heading="Labels across every reply",
                intro="Expressed disposition, read from text. A reply expresses a label when"
                " the panel's median intensity is 1 or more; intervals are 95% Wilson"
                " intervals.",
                header=["Label", "Family", "Replies", "Share", "Mean intensity", "Disputed"],
                rows=[
                    [
                        share.label.replace("_", " "),
                        share.family,
                        f"{share.expressed} of {share.replies}",
                        _percent(share.share)
                        + (
                            f" ({_percent(share.interval.low)} to {_percent(share.interval.high)})"
                            if share.interval
                            else ""
                        ),
                        f"{share.mean_intensity:.2f}",
                        str(share.disputed),
                    ]
                    for share in shares
                ],
            ),
            Section(
                heading="Judges",
                header=["Judge", "Findings kept", "Findings dropped"],
                rows=[
                    [
                        judge,
                        str(kept.get(judge, 0)),
                        str(sum(1 for d in ethos.dropped if d.judge_model == judge)),
                    ]
                    for judge in ethos.judges
                ],
            ),
        ]
    if run.kind == RunKind.scenarios.value:
        found = (
            await db.execute(select(ScenarioSet).where(ScenarioSet.run_id == run.id))
        ).scalar_one_or_none()
        scenarios = (found.content.get("scenarios") or []) if found else []
        return [
            Section(
                heading="Scenarios generated",
                intro=f"Presence is scored on {found.presence_dimension}." if found else None,
                header=["Scenario", "Variation"],
                rows=[[s["name"], s.get("variation") or "base"] for s in scenarios],
            )
        ]
    if run.kind == RunKind.witness.value:
        from agora_api.routes.witness import read_witness_run

        page = await read_witness_run(run.id, user, db, settings)
        compared = (
            f"Compared with the Ethos run {page.ethos_run.title}. "
            if page.ethos_run
            else "No finished Ethos run reads the same source, so there is nothing to compare. "
        )
        sections = [
            Section(
                heading="Signals beside Ethos labels",
                intro=f"How {page.reader.model}, an open-weight model, reads the text; not the"
                f" target model's internals. {compared}Ethos counts a label in a reply when the"
                " panel's median intensity is 1 or more; a signal counts when any token"
                " reaches its threshold.",
                header=[
                    "Signal",
                    "Kind",
                    "Label",
                    "Both",
                    "Ethos only",
                    "Signal only",
                    "Neither",
                    "Agree",
                ],
                rows=[
                    [
                        a.signal.replace("_", " "),
                        a.kind.replace("_", " "),
                        a.label.replace("_", " "),
                        str(len(a.both)),
                        str(len(a.ethos_only)),
                        str(len(a.witness_only)),
                        str(len(a.neither)),
                        _percent(a.agreement),
                    ]
                    for a in page.agreements
                ],
            )
        ]
        if page.dropped:
            sections.append(
                Section(
                    heading="Signals dropped",
                    intro="Signals that failed the checks in code are kept out of every count.",
                    header=["Reason", "Signals"],
                    rows=[[k.replace("_", " "), str(n)] for k, n in page.dropped.items()],
                )
            )
        return sections
    return []


@router.get("/runs/{run_id}/report.pdf", response_class=Response)
async def export_report(
    run_id: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> Response:
    """A printable report of one run, opening with its full provenance."""
    run = await db.get(Run, run_id)
    if run is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No such run.")
    pdf = run_report(
        run, generated_by=user.email, sections=await _sections(db, run, settings, user)
    )
    await _audited(db, user, run, "pdf", 1)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="agora-{run.kind}-{run.id}.pdf"'},
    )


# Comparing two Ethos runs: the compare view, exported.
SHARE_FIELDS = ("replies", "expressed", "share", "low", "high")
COMPARISON_FIELDS = (
    "label",
    "family",
    "shared_scenarios",
    *(
        f"{side}_{name}"
        for side in "ab"
        for name in ("replies", "expressed", "share", "low", "high")
    ),
    "difference",
    "difference_low",
    "difference_high",
    *(f"{side}_{name}" for side in "ab" for name in PROVENANCE),
)


def _points(value: float) -> str:
    """Percentage points with a sign, as on screen: +20, -5, or 0."""
    whole = round(value * 100)
    return f"+{whole}" if whole > 0 else str(whole)


def _number(value: float | None) -> str:
    return "" if value is None else f"{value:.4f}"


def _interval(interval: IntervalOut | None) -> tuple[str, str]:
    return ("", "") if interval is None else (_number(interval.low), _number(interval.high))


async def _comparison_audited(db: Db, user: User, a: Run, b: Run, fmt: str, rows: int) -> None:
    await audit.record(
        db,
        "report.export",
        actor_id=user.id,
        target_type="run",
        target_id=a.id,
        detail={"format": fmt, "compared_with": str(b.id), "rows": rows},
    )
    await db.commit()


@router.get("/compare.csv", response_class=Response)
async def export_comparison(
    a: uuid.UUID, b: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> Response:
    """One row per label, A beside B on the scenarios both read, each row carrying both
    runs' provenance. It counts what the compare view counts for this reader."""
    comparison, run_a, run_b = await build_comparison(db, settings, user, a, b)
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=COMPARISON_FIELDS)
    writer.writeheader()
    shared = {
        **{f"a_{k}": v for k, v in provenance(run_a).items()},
        **{f"b_{k}": v for k, v in provenance(run_b).items()},
    }
    for row in comparison.labels:
        a_low, a_high = _interval(row.a.interval)
        b_low, b_high = _interval(row.b.interval)
        d_low, d_high = _interval(row.difference_interval)
        writer.writerow(
            {
                "label": row.label,
                "family": row.family,
                "shared_scenarios": comparison.shared_scenarios,
                "a_replies": row.a.replies,
                "a_expressed": row.a.expressed,
                "a_share": _number(row.a.share),
                "a_low": a_low,
                "a_high": a_high,
                "b_replies": row.b.replies,
                "b_expressed": row.b.expressed,
                "b_share": _number(row.b.share),
                "b_low": b_low,
                "b_high": b_high,
                "difference": _number(row.difference),
                "difference_low": d_low,
                "difference_high": d_high,
                **shared,
            }
        )
    await _comparison_audited(db, user, run_a, run_b, "compare.csv", len(comparison.labels))
    return Response(
        buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="agora-compare-{a}-{b}.csv"'},
    )


def _share(item: LabelPrevalenceOut) -> str:
    """A share with its count and interval, such as "40% (4 of 10; 17% to 69%)"."""
    if item.share is None:
        return "No replies"
    text = f"{_percent(item.share)} ({item.expressed} of {item.replies}"
    if item.interval is not None:
        text += f"; {_percent(item.interval.low)} to {_percent(item.interval.high)}"
    return text + ")"


def _comparison_sections(comparison: EthosCompareOut) -> list[Section]:
    rows = []
    for row in comparison.labels:
        if row.difference is None:
            change = "Not comparable"
        elif row.difference_interval is None:
            change = f"{_points(row.difference)} points"
        else:
            low, high = row.difference_interval.low, row.difference_interval.high
            change = f"{_points(row.difference)} points ({_points(low)} to {_points(high)})"
        label = row.label.replace("_", " ").capitalize()
        rows.append([label, row.family, _share(row.a), _share(row.b), change])
    fits = [
        [
            item.scenario_key.split("/")[-1].replace("_", " ").replace("-", " ").capitalize(),
            "No fit" if item.a_fit is None else _percent(item.a_fit),
            "No fit" if item.b_fit is None else _percent(item.b_fit),
        ]
        for item in comparison.scenarios
    ]
    return [
        Section(
            heading="Labels",
            intro=(
                f"The share of replies expressing each label on the {comparison.shared_scenarios} "
                "scenarios both runs read, with 95% Wilson intervals. The change is B minus A, "
                "in percentage points, with Newcombe's 95% interval; where it spans zero, the "
                "difference may be noise. Expressed dispositions are read from text; Ethos does "
                "not see inside the model."
            ),
            header=["Label", "Family", "A", "B", "B minus A"],
            rows=rows,
        ),
        Section(
            heading="Fit by scenario",
            intro="How well each scenario's replies matched what it expects, in each run.",
            header=["Scenario", "A", "B"],
            rows=fits,
            note=(
                "Conversations with content notes the reader has not opted in to are left out, "
                "as they are on screen."
            ),
        ),
    ]


@router.get("/compare.pdf", response_class=Response)
async def export_comparison_report(
    a: uuid.UUID, b: uuid.UUID, user: ReaderUser, db: Db, settings: AppSettings
) -> Response:
    """The compare view as a printable report, opening with both runs' provenance."""
    comparison, run_a, run_b = await build_comparison(db, settings, user, a, b)
    pdf = comparison_report(
        run_a, run_b, generated_by=user.email, sections=_comparison_sections(comparison)
    )
    await _comparison_audited(db, user, run_a, run_b, "compare.pdf", 1)
    return Response(
        pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="agora-compare-{a}-{b}.pdf"'},
    )
