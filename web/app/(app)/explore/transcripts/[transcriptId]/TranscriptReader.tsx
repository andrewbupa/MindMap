"use client";

import Link from "next/link";
import { Fragment, useEffect, useRef, useState } from "react";

import { FullThinking } from "@/components/runs/FullThinking";
import { MessageView } from "@/components/runs/Messages";
import styles from "@/components/runs/runs.module.css";
import { Badge, Card, LinkButton, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { transcriptLog, type DimensionOut, type TranscriptOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const CITE = /(\[M\d+\])/;
const IS_CITE = /^\[M\d+\]$/;

/** Judge text with each [Mn] citation linked to the message it cites. */
function Cited({ text, cites }: { text: string; cites: Map<string, number | null> }) {
  return (
    <>
      {text.split(CITE).map((part, index) => {
        if (!IS_CITE.test(part)) return <Fragment key={index}>{part}</Fragment>;
        const target = cites.get(part);
        return target === undefined || target === null ? (
          <span key={index} title="Cites a message from a branch the auditor rolled back">
            {part}
          </span>
        ) : (
          <a key={index} href={`#m-${target}`}>
            {part}
          </a>
        );
      })}
    </>
  );
}

function ScoreTable({
  scores,
  byName,
}: {
  scores: TranscriptOut["scores"];
  byName: Map<string, DimensionOut>;
}) {
  return (
    <table>
      <tbody>
        {scores.map((score) => {
          const dimension = byName.get(score.dimension);
          const high = score.value >= 7;
          const tone = high ? (dimension?.palette === "good-high" ? "ok" : "danger") : "neutral";
          return (
            <tr key={score.id} id={`score-${score.dimension}`}>
              <th scope="row" title={dimension?.description}>
                {dimension?.display_name ?? sentenceCase(score.dimension.replaceAll("_", " "))}
              </th>
              <td>
                <Badge tone={tone}>
                  {score.value} of {score.scale_max}
                </Badge>
              </td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

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
  const cited = new Set(transcript.references.map((r) => r.message_index));
  const byName = new Map(dimensions.map((d) => [d.name, d]));
  const scores = [...transcript.scores].sort((a, b) => {
    const left = byName.get(a.dimension);
    const right = byName.get(b.dimension);
    return Number(right?.custom) - Number(left?.custom) || a.dimension.localeCompare(b.dimension);
  });
  const explanation = transcript.scores[0]?.explanation;
  const measure = transcript.run.kind === "measure";
  const presence = measure ? String(transcript.run.config.presence_dimension ?? "") : null;
  const runHref = `/${measure ? "measure" : "explore"}/runs/${transcript.run.id}`;
  const scenarioName = (transcript.scenario_key ?? "Transcript").split("/").pop() ?? "Transcript";
  const leading = scores.filter((s) => (measure ? s.dimension === presence : byName.get(s.dimension)?.custom));
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
    const { data } = await transcriptLog({
      client: browserClient,
      path: { transcript_id: transcript.id },
    });
    if (data) window.location.assign(data.url);
    else setError("The log could not be opened.");
  }

  return (
    <>
      <PageHeader title={sentenceCase(scenarioName.replaceAll("-", " ").replaceAll("_", " "))}>
        <p>
          From <Link href={runHref}>{transcript.run.title}</Link>
          {transcript.epoch > 1 ? `, repetition ${transcript.epoch}` : ""}.{" "}
          <LinkButton onClick={openLog}>Download the Inspect log</LinkButton> to open it in Inspect
          View.
        </p>
        {error ? <Notice tone="danger">{error}</Notice> : null}
      </PageHeader>
      {transcript.content_notes.map((note) => (
        <Notice key={note}>Content note: {sentenceCase(note)}.</Notice>
      ))}
      <div className={styles.layout}>
        <section aria-label="Conversation">
          {transcript.seed_text ? (
            <details className={styles.system}>
              <summary>The seed the auditor followed</summary>
              <p>{transcript.seed_text}</p>
            </details>
          ) : null}
          <div className={styles.thread}>
            {transcript.messages.map((message) => (
              <MessageView
                key={message.id}
                message={message}
                cited={cited.has(message.index)}
                speaker="Member (played by the auditor)"
              />
            ))}
          </div>
        </section>
        <aside className={styles.pane}>
          <Card title="Judge's summary">
            {transcript.judge_refused ? (
              <Notice tone="danger">The judge declined to score this transcript.</Notice>
            ) : null}
            {transcript.summary ? (
              <p>
                <Cited text={transcript.summary} cites={cites} />
              </p>
            ) : null}
            {transcript.highlights ? (
              <>
                <h3>Highlights</h3>
                <p className={styles.thinking}>
                  <Cited text={transcript.highlights} cites={cites} />
                </p>
              </>
            ) : null}
            {explanation ? (
              <details>
                <summary>The judge&apos;s reasons</summary>
                <p className={styles.thinking}>
                  <Cited text={explanation} cites={cites} />
                </p>
              </details>
            ) : null}
          </Card>
          <Card title="Scores">
            {measure ? (
              <p className={styles.quiet}>
                Presence of the behaviour; the rate counts {String(transcript.run.config.threshold ?? 7)} or
                more.
              </p>
            ) : null}
            <ScoreTable scores={leading} byName={byName} />
            <details ref={builtins}>
              <summary>{measure ? "Realism and evaluation awareness" : "Petri\u2019s built-in dimensions"}</summary>
              <ScoreTable scores={rest} byName={byName} />
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
