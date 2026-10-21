"use client";

import Link from "next/link";
import { useState } from "react";

import { MessageView } from "@/components/runs/Messages";
import runStyles from "@/components/runs/runs.module.css";
import { Badge, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import type { AnnotationOut, LensTranscriptOut, MessageOut } from "@/lib/api";

import { LENS_QUIET, familyColour, formatMedian, intensityName, labelName } from "./family";
import { Highlighted, type Mark } from "./Highlighted";
import styles from "./lens.module.css";
import { ProfileStrip } from "./ProfileStrip";
import { TurnTimeline } from "./TurnTimeline";

type Selection = { messageId: string; label: string } | null;

function marksFor(
  data: LensTranscriptOut,
  message: MessageOut,
  channel: "content" | "thinking_summary",
): Mark[] {
  const reply = data.replies.find((r) => r.message_id === message.id);
  return data.annotations
    .filter((a) => a.message_id === message.id && a.channel === channel)
    .map((a) => ({
      id: a.id,
      start: a.start,
      end: a.end,
      label: a.label,
      family: a.family,
      // Replies tint by the panel's median; thinking summaries by each finding.
      intensity:
        channel === "content"
          ? (reply?.labels.find((l) => l.label === a.label)?.median ?? a.intensity)
          : a.intensity,
    }));
}

/**
 * The response view: each reply with its quoted phrases tinted by family, a profile
 * strip under it with the expected profile behind, the panel's findings in a side
 * pane, thinking summaries in their own pane, and the turn timeline below.
 */
export function TranscriptLens({ data }: { data: LensTranscriptOut }) {
  const [selected, setSelected] = useState<Selection>(null);
  const labels = new Map(data.labels.map((l) => [l.key, l]));
  const replyIds = new Set(data.replies.map((r) => r.message_id));
  const chosen = selected
    ? data.annotations.filter(
        (a) => a.message_id === selected.messageId && a.label === selected.label,
      )
    : [];
  const chosenReply = selected ? data.replies.find((r) => r.message_id === selected.messageId) : null;
  const consensus = chosenReply?.labels.find((l) => l.label === selected?.label);
  const label = selected ? labels.get(selected.label) : null;
  const summaries = data.messages.filter((m) => m.role === "assistant" && m.thinking_summary);
  const scenario = (data.scenario_key ?? "Transcript").split("/").pop() ?? "Transcript";

  function byJudge(found: AnnotationOut[]) {
    return data.judges.map((judge) => ({
      judge,
      intensity: consensus?.by_judge[judge] ?? 0,
      quotes: found.filter((a) => a.judge === judge && a.channel === "content"),
    }));
  }

  return (
    <>
      <PageHeader title={sentenceCase(scenario.replaceAll("_", " ").replaceAll("-", " "))} quiet={LENS_QUIET}>
        <p>
          Read by <Link href={`/lens/runs/${data.run.id}`}>{data.run.title}</Link>, from{" "}
          {data.source.title}. Scenario type:{" "}
          {data.scenario_type ? sentenceCase(data.scenario_type.replaceAll("_", " ")) : "none, so no fit"}.
        </p>
      </PageHeader>
      {data.content_notes.map((note) => (
        <Notice key={note}>Content note: {sentenceCase(note)}.</Notice>
      ))}
      <div className={runStyles.layout}>
        <section aria-label="Conversation">
          {data.seed_text ? (
            <details className={runStyles.system}>
              <summary>The scenario the conversation followed</summary>
              <p>{data.seed_text}</p>
            </details>
          ) : null}
          <div className={runStyles.thread}>
            {data.messages.map((message) => {
              const reply = data.replies.find((r) => r.message_id === message.id);
              if (!reply || !replyIds.has(message.id)) {
                return (
                  <MessageView key={message.id} message={message} speaker="Member (played by the auditor)" />
                );
              }
              return (
                <div key={message.id} id={`r-${message.id}`} className={`${runStyles.bubble} ${runStyles.assistant}`}>
                  <div className={runStyles.role}>
                    Agent, reply {data.replies.indexOf(reply) + 1}
                    {reply.fit?.score !== null && reply.fit?.score !== undefined
                      ? `, fit ${Math.round(reply.fit.score * 100)}%`
                      : ""}
                  </div>
                  <Highlighted
                    text={message.content}
                    marks={marksFor(data, message, "content")}
                    selected={selected?.messageId === message.id ? selected.label : null}
                    onSelect={(key) => setSelected({ messageId: message.id, label: key })}
                  />
                  <ProfileStrip
                    reply={reply}
                    expected={data.expected}
                    labels={data.labels}
                    annotations={data.annotations}
                    onSelect={(key) => setSelected({ messageId: message.id, label: key })}
                  />
                </div>
              );
            })}
          </div>
        </section>
        <aside className={`${runStyles.pane} ${styles.detail}`}>
          <Card title="Finding">
            {!selected || !label ? (
              <p className={styles.quiet}>
                Choose a highlighted phrase or a cell in a reply&apos;s strip to see what each judge
                found. ✓ expected and found, – expected but missing, ! expected absent but found,
                ⚑ judges differ by two points or more.
              </p>
            ) : (
              <>
                <p>
                  <span className={styles.swatch} style={{ background: familyColour(label.family) }} />
                  <strong>{labelName(label.key)}</strong> <Badge>{sentenceCase(label.family)}</Badge>{" "}
                  <Badge tone={label.trust_status === "trusted" ? "ok" : "neutral"}>
                    {sentenceCase(label.trust_status)}
                  </Badge>
                </p>
                <p className={styles.quiet}>{label.definition}</p>
                <p>
                  Panel median: <strong>{intensityName(consensus?.median ?? 0)}</strong> (
                  {formatMedian(consensus?.median ?? 0)} of 3)
                  {consensus?.disputed ? (
                    <>
                      {" "}
                      <Badge tone="warn">Judges differ by two or more</Badge>
                    </>
                  ) : null}
                </p>
                <table>
                  <tbody>
                    {byJudge(chosen).map((row) => (
                      <tr key={row.judge}>
                        <th scope="row">{row.judge}</th>
                        <td>
                          {intensityName(row.intensity)} ({row.intensity})
                          {row.quotes.map((quote) => (
                            <div key={quote.id}>
                              <a href={`#a-${quote.id}`}>&ldquo;{quote.quote}&rdquo;</a>
                              <div className={styles.quiet}>{quote.rationale}</div>
                            </div>
                          ))}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </>
            )}
          </Card>
          <Card title="Thinking summaries">
            <p className={styles.quiet}>
              Summaries of the agent&apos;s reasoning, written by a separate model. Findings here are
              shown for reading and never count towards fit.
            </p>
            {summaries.length === 0 ? <p>No reply in this conversation has a thinking summary.</p> : null}
            {summaries.map((message) => (
              <div key={message.id} className={styles.thinking}>
                <a href={`#r-${message.id}`}>
                  Summary for reply{" "}
                  {data.replies.findIndex((r) => r.message_id === message.id) + 1 || "with a tool call"}
                </a>
                <Highlighted
                  text={message.thinking_summary ?? ""}
                  marks={marksFor(data, message, "thinking_summary")}
                />
              </div>
            ))}
          </Card>
          <Card title="Panel">
            <ul>
              {data.judges.map((judge) => (
                <li key={judge}>{judge}</li>
              ))}
            </ul>
            {data.dropped.length ? (
              <p className={styles.quiet}>
                Dropped in this conversation:{" "}
                {data.dropped.map((d) => `${d.count} from ${d.judge} (${d.reason.replaceAll("_", " ")})`).join("; ")}
                .
              </p>
            ) : (
              <p className={styles.quiet}>Every quote in this conversation was found in its reply.</p>
            )}
          </Card>
        </aside>
      </div>
      <Card title="Turn timeline">
        <TurnTimeline
          replies={data.replies}
          expected={data.expected}
          labels={data.labels}
          annotations={data.annotations}
        />
      </Card>
    </>
  );
}
