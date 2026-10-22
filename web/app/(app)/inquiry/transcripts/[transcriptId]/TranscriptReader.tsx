"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { ScoreCell } from "@/components/data/ScoreCell";
import { Cited } from "@/components/runs/Cited";
import { ContentNote } from "@/components/runs/ContentNote";
import { FullThinking } from "@/components/runs/FullThinking";
import { Fold, MessageView } from "@/components/runs/Messages";
import { Button, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { transcriptLog, type DimensionOut, type TranscriptOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

function ScoreTable({ scores, byName }: { scores: TranscriptOut["scores"]; byName: Map<string, DimensionOut> }) {
  const rows: Row[] = scores.map((score) => {
    const dimension = byName.get(score.dimension);
    const name = dimension?.display_name ?? sentenceCase(score.dimension.replaceAll("_", " "));
    return {
      id: score.id,
      cells: {
        dimension: (
          <span id={`score-${score.dimension}`} title={dimension?.description}>
            {name}
          </span>
        ),
        score: (
          <ScoreCell value={score.value} max={score.scale_max} label={name} concern={dimension?.palette !== "good-high"} />
        ),
      },
      sort: { dimension: name, score: score.value },
    };
  });
  return (
    <DataTable
      density="dense"
      columns={[
        { key: "dimension", label: "Dimension" },
        { key: "score", label: "Score" },
      ]}
      rows={rows}
    />
  );
}

/** One scored conversation: the route of messages, the judge's account with its citations, and the scores. */
export function TranscriptReader({
  transcript,
  dimensions,
  canReadFullThinking = false,
}: {
  transcript: TranscriptOut;
  dimensions: DimensionOut[];
  canReadFullThinking?: boolean;
}) {
  const [error, setError] = useState<string | null>(null);
  const builtins = useRef<HTMLDetailsElement>(null);
  const cites = new Map(transcript.references.map((r) => [r.cite ?? "", r.message_index]));
  // The judge's own name for each message it cited, such as M3.
  const references = new Map(
    transcript.references
      .filter((r) => r.message_index !== null && r.message_index !== undefined && r.cite)
      .map((r) => [r.message_index as number, (r.cite ?? "").replace(/[[\]]/g, "")]),
  );
  const byName = new Map(dimensions.map((d) => [d.name, d]));
  const scores = [...transcript.scores].sort((a, b) => {
    const left = byName.get(a.dimension);
    const right = byName.get(b.dimension);
    return Number(right?.custom) - Number(left?.custom) || a.dimension.localeCompare(b.dimension);
  });
  const explanation = transcript.scores[0]?.explanation;
  const tally = transcript.run.kind === "tally";
  const presence = tally ? String(transcript.run.config.presence_dimension ?? "") : null;
  const runHref = `/${tally ? "tally" : "inquiry"}/runs/${transcript.run.id}`;
  const scenarioName = (transcript.scenario_key ?? "Transcript").split("/").pop() ?? "Transcript";
  const leading = scores.filter((s) => (tally ? s.dimension === presence : byName.get(s.dimension)?.custom));
  const rest = scores.filter((s) => !leading.includes(s));

  // A heatmap cell links to #score-<dimension>; open the built-ins if that is where it points.
  useEffect(() => {
    const target = window.location.hash.replace("#score-", "");
    const builtin = dimensions.some((d) => d.name === target && !d.custom);
    if (builtin && builtins.current) {
      builtins.current.open = true;
      document.getElementById(`score-${target}`)?.scrollIntoView();
    }
  }, [dimensions]);

  async function openLog() {
    setError(null);
    const { data } = await transcriptLog({ client: browserClient, path: { transcript_id: transcript.id } });
    if (data) window.location.assign(data.url);
    else setError("The log could not be opened. It is written when the sample finishes; try again shortly.");
  }

  return (
    <>
      <PageHeader
        title={sentenceCase(scenarioName.replaceAll("-", " ").replaceAll("_", " "))}
        actions={
          <Button variant="secondary" onClick={openLog}>
            Download the Inspect log
          </Button>
        }
      >
        <p>
          From <Link href={runHref}>{transcript.run.title}</Link>
          {transcript.epoch > 1 ? `, repetition ${transcript.epoch}` : ""}. Open the log in Inspect View for the full
          detail.
        </p>
      </PageHeader>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {transcript.content_notes.map((note) => (
        <ContentNote key={note} topic={note} />
      ))}
      <div className="ag-split">
        <section aria-label="Conversation">
          {transcript.seed_text ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <Fold summary="Show the seed the auditor followed">{transcript.seed_text}</Fold>
            </div>
          ) : null}
          <div className="ag-route">
            {transcript.messages.map((message) => (
              <MessageView
                key={message.id}
                message={message}
                reference={references.get(message.index)}
                cited={references.has(message.index)}
              />
            ))}
          </div>
        </section>
        <aside aria-label="The judge's account">
          <Card title="Judge's summary">
            {transcript.judge_refused ? <Notice tone="danger">The judge declined to score this transcript.</Notice> : null}
            {transcript.summary ? <Cited text={transcript.summary} cites={cites} /> : null}
            {transcript.highlights ? (
              <>
                <h3 style={{ marginTop: "var(--space-4)" }}>Highlights</h3>
                <Cited text={transcript.highlights} cites={cites} />
              </>
            ) : null}
            {explanation ? (
              <div style={{ marginTop: "var(--space-4)" }}>
                <Fold summary="The judge's reasons">
                  <Cited text={explanation} cites={cites} />
                </Fold>
              </div>
            ) : null}
          </Card>
          <Card title="Scores">
            {tally ? (
              <p className="ag-pane-def">
                Presence of the behaviour; the rate counts {String(transcript.run.config.threshold ?? 7)} or more.
              </p>
            ) : null}
            <ScoreTable scores={leading} byName={byName} />
            <details ref={builtins} className="ag-fold" style={{ marginTop: "var(--space-3)" }}>
              <summary>{tally ? "Realism and evaluation awareness" : "Petri’s built-in dimensions"}</summary>
              <div style={{ marginTop: "var(--space-2)" }}>
                <ScoreTable scores={rest} byName={byName} />
              </div>
            </details>
          </Card>
          {transcript.messages.some((message) => message.has_full_thinking) ? (
            <FullThinking transcriptId={transcript.id} allowed={canReadFullThinking} />
          ) : null}
        </aside>
      </div>
    </>
  );
}
