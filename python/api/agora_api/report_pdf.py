"""PDF run reports, built with ReportLab's Platypus.

Every report opens with the run's provenance, in full, so a printed page can be
traced to the exact commit, configuration, prompt, seeds, taxonomy and models. The
sections that follow depend on the kind of run.
"""

from __future__ import annotations

import io
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from reportlab.platypus.flowables import Flowable

from agora_core.models import Run

GRID = colors.HexColor("#e2ded6")
HEADER = colors.HexColor("#f3f1ed")
MUTED = colors.HexColor("#5f5b54")


@dataclass
class Section:
    heading: str
    intro: str | None = None
    header: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    note: str | None = None


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle("AgoraTitle", parent=base["Title"], fontSize=16, alignment=0),
        "heading": ParagraphStyle("AgoraHeading", parent=base["Heading2"], fontSize=12),
        "body": ParagraphStyle("AgoraBody", parent=base["BodyText"], fontSize=9, leading=12),
        "cell": ParagraphStyle("AgoraCell", parent=base["BodyText"], fontSize=8, leading=10),
        "mono": ParagraphStyle(
            "AgoraMono", parent=base["BodyText"], fontName="Courier", fontSize=7.5, leading=10
        ),
        "quiet": ParagraphStyle(
            "AgoraQuiet", parent=base["BodyText"], fontSize=8, leading=10, textColor=MUTED
        ),
    }


def _table(
    header: list[str],
    rows: list[list[str]],
    style: ParagraphStyle,
    width: float,
    widths: list[float] | None = None,
    value_style: ParagraphStyle | None = None,
) -> Table:
    """A table of wrapped paragraphs. ``widths`` are shares of the width; ``value_style``
    sets every column after the first, such as a monospace face for hashes."""
    later = value_style or style
    data = [[Paragraph(f"<b>{escape(h)}</b>", style) for h in header]] + [
        [Paragraph(escape(str(cell)), style if i == 0 else later) for i, cell in enumerate(row)]
        for row in rows
    ]
    columns = len(header) or 1
    shares = widths or [1 / columns] * columns
    table = Table(data, colWidths=[width * share for share in shares], repeatRows=1, hAlign="LEFT")
    table.setStyle(
        TableStyle(
            [
                ("GRID", (0, 0), (-1, -1), 0.5, GRID),
                ("BACKGROUND", (0, 0), (-1, 0), HEADER),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    return table


def provenance_rows(run: Run) -> list[list[str]]:
    return [
        ["Run", str(run.id)],
        ["Kind", run.kind],
        ["Status", run.status],
        ["Git commit", run.git_commit],
        ["Config hash", run.config_hash],
        ["Prompt SHA-256", run.prompt_sha or "Not applicable"],
        ["Seed hash", run.seed_hash or "Not applicable"],
        ["Taxonomy version", run.taxonomy_version or "Not applicable"],
        ["Models", json.dumps(run.model_ids, sort_keys=True)],
        ["Engines", json.dumps(run.engine_versions, sort_keys=True)],
        ["Route", run.route or "Not applicable"],
        ["Tokens", f"{run.tokens_used:,} of {run.token_budget:,}"],
        ["Estimated cost", f"US${float(run.cost_usd):.4f}"],
        ["Started", run.started_at.isoformat() if run.started_at else "Not started"],
        ["Finished", run.finished_at.isoformat() if run.finished_at else "Not finished"],
    ]


def run_report(run: Run, *, generated_by: str, sections: list[Section]) -> bytes:
    return _report(run.title, [("Provenance", run)], generated_by, sections)


def comparison_report(a: Run, b: Run, *, generated_by: str, sections: list[Section]) -> bytes:
    """Two runs side by side, each with its full provenance, then the comparison."""
    return _report(
        f"Comparison: {a.title} beside {b.title}",
        [(f"Provenance of A: {a.title}", a), (f"Provenance of B: {b.title}", b)],
        generated_by,
        sections,
    )


def _report(
    title: str, runs: list[tuple[str, Run]], generated_by: str, sections: list[Section]
) -> bytes:
    buffer = io.BytesIO()
    styles = _styles()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=18 * mm,
        rightMargin=18 * mm,
        topMargin=18 * mm,
        bottomMargin=18 * mm,
        title=f"Agora report: {title}",
        author="Agora",
    )
    width = doc.width
    story: list[Flowable] = [
        Paragraph(escape(title), styles["title"]),
        Paragraph(
            escape(
                f"Agora report, generated {datetime.now(UTC):%d %B %Y, %H:%M} UTC for "
                f"{generated_by}. Everything in Agora is synthetic: no real personal or "
                "health data."
            ),
            styles["quiet"],
        ),
    ]
    for heading, run in runs:
        story += [
            Spacer(1, 6 * mm),
            Paragraph(escape(heading), styles["heading"]),
            _table(
                ["Field", "Value"],
                provenance_rows(run),
                styles["cell"],
                width,
                widths=[0.22, 0.78],
                value_style=styles["mono"],
            ),
        ]
    for section in sections:
        story += [Spacer(1, 5 * mm), Paragraph(escape(section.heading), styles["heading"])]
        if section.intro:
            story.append(Paragraph(escape(section.intro), styles["body"]))
            story.append(Spacer(1, 2 * mm))
        if section.header:
            story.append(_table(section.header, section.rows, styles["cell"], width))
        if section.note:
            story += [Spacer(1, 2 * mm), Paragraph(escape(section.note), styles["quiet"])]
    doc.build(story)
    return buffer.getvalue()
