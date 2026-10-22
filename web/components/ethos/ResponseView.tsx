"use client";

import Link from "next/link";
import { useState } from "react";

import { ContentNote } from "@/components/runs/ContentNote";
import { Fold, MessageFrame, MessageView } from "@/components/runs/Messages";
import { Badge, Card, PageHeader, sentenceCase } from "@/components/ui";
import type { EthosTranscriptOut, MessageOut, WitnessTranscriptOut } from "@/lib/api";

import { ETHOS_NOTE } from "./family";
import { FindingPane } from "./FindingPane";
import { Highlighted, type Mark } from "./Highlighted";
import { ProfileStrip } from "./ProfileStrip";
import { TurnTimeline } from "./TurnTimeline";
import { WitnessPane } from "./WitnessPane";

type Selection = { messageId: string; label: string } | null;

function marksFor(data: EthosTranscriptOut, message: MessageOut, channel: "content" | "thinking_summary"): Mark[] {
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
        channel === "content" ? (reply?.labels.find((l) => l.label === a.label)?.median ?? a.intensity) : a.intensity,
    }));
}

/**
 * The response view: each reply on the conversation's route with its quoted phrases tinted
 * by family and its profile strip against the expected profile; the chosen finding,
 * thinking summaries and open-model signals in the side pane; the turn timeline below.
 */
export function ResponseView({ data, witness = null }: { data: EthosTranscriptOut; witness?: WitnessTranscriptOut | null }) {
  const [selected, setSelected] = useState<Selection>(null);
  const labels = new Map(data.labels.map((l) => [l.key, l]));
  const chosenReply = selected ? data.replies.find((r) => r.message_id === selected.messageId) : null;
  const label = selected ? labels.get(selected.label) : null;
  const summaries = data.messages.filter((m) => m.role === "assistant" && m.thinking_summary);
  const scenario = (data.scenario_key ?? "Transcript").split("/").pop() ?? "Transcript";
  const fit = (score: number | null | undefined) => (score === null || score === undefined ? null : Math.round(score * 100));

  return (
    <>
      <PageHeader title={sentenceCase(scenario.replaceAll("_", " ").replaceAll("-", " "))} note={ETHOS_NOTE}>
        <p>
          Each reply with its fit, the phrases the judges found, and how they compare with what this scenario expects.
          Read by <Link href={`/ethos/runs/${data.run.id}`}>{data.run.title}</Link>, from {data.source.title}. Scenario
          type: {data.scenario_type ? sentenceCase(data.scenario_type.replaceAll("_", " ")) : "none, so no fit"}.
        </p>
      </PageHeader>
      {data.content_notes.map((note) => (
        <ContentNote key={note} topic={note} />
      ))}
      <div className="ag-split">
        <section aria-label="Conversation">
          {data.seed_text ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <Fold summary="Show the scenario the conversation followed">{data.seed_text}</Fold>
            </div>
          ) : null}
          <div className="ag-route">
            {data.messages.map((message) => {
              const reply = data.replies.find((r) => r.message_id === message.id);
              if (!reply) return <MessageView key={message.id} message={message} />;
              const number = data.replies.indexOf(reply) + 1;
              const score = fit(reply.fit?.score);
              return (
                <MessageFrame
                  key={message.id}
                  id={`r-${message.id}`}
                  role="agent"
                  index={message.index}
                  author={`Agent, reply ${number}`}
                  badges={
                    <>
                      {score !== null ? <Badge tone={score >= 70 ? "ok" : score >= 40 ? "neutral" : "warn"}>Fit {score}%</Badge> : null}
                      {message.thinking_summary ? <Badge>Thinking summary</Badge> : null}
                    </>
                  }
                  selected={selected?.messageId === message.id}
                >
                  <div className="ag-msg-body" id={`m-${message.index}`}>
                    <Highlighted
                      text={message.content}
                      marks={marksFor(data, message, "content")}
                      selected={selected?.messageId === message.id ? selected.label : null}
                      onSelect={(key) => setSelected({ messageId: message.id, label: key })}
                      judges={data.judges.length}
                    />
                  </div>
                  <div style={{ marginTop: "var(--space-3)" }}>
                    <ProfileStrip
                      reply={reply}
                      expected={data.expected}
                      labels={data.labels}
                      annotations={data.annotations}
                      onSelect={(key) => setSelected({ messageId: message.id, label: key })}
                    />
                  </div>
                </MessageFrame>
              );
            })}
          </div>
        </section>
        <aside aria-label="Findings and signals">
          {selected && label ? (
            <FindingPane
              label={label}
              consensus={chosenReply?.labels.find((l) => l.label === selected.label)}
              judges={data.judges}
              annotations={data.annotations.filter((a) => a.message_id === selected.messageId && a.label === selected.label)}
              onClose={() => setSelected(null)}
            />
          ) : (
            <Card title="Finding">
              <p className="ag-pane-def">
                Choose a highlighted phrase, or a label in a reply&apos;s strip, to see what each judge found. ✓
                expected and found, – expected but missing, ! expected absent but found, ⚑ judges differ by two
                points or more.
              </p>
            </Card>
          )}
          <Card title="Thinking summaries">
            <p className="ag-pane-def">
              Summaries of the agent&apos;s reasoning, written by a separate model. Findings here are shown for reading
              and never count towards fit.
            </p>
            {summaries.length === 0 ? <p>No reply in this conversation has a thinking summary.</p> : null}
            {summaries.map((message) => (
              <div key={message.id} style={{ marginTop: "var(--space-3)" }}>
                <a href={`#r-${message.id}`}>
                  Summary for reply {data.replies.findIndex((r) => r.message_id === message.id) + 1 || "with a tool call"}
                </a>
                <div className="ag-fold-body">
                  <Highlighted text={message.thinking_summary ?? ""} marks={marksFor(data, message, "thinking_summary")} />
                </div>
              </div>
            ))}
          </Card>
          {witness ? (
            <WitnessPane
              data={witness}
              runHref={`/ethos/witness/${witness.run.id}?ethos_run=${data.run.id}`}
              replies={data.replies.map((reply, index) => ({
                id: reply.message_id,
                number: index + 1,
                text: data.messages.find((m) => m.id === reply.message_id)?.content ?? "",
              }))}
            />
          ) : null}
          <Card title="Panel">
            <ul style={{ margin: 0, paddingLeft: "var(--space-4)" }}>
              {data.judges.map((judge) => (
                <li key={judge}>{judge}</li>
              ))}
            </ul>
            <p className="ag-pane-def" style={{ marginTop: "var(--space-3)" }}>
              {data.dropped.length
                ? `Dropped in this conversation: ${data.dropped
                    .map((d) => `${d.count} from ${d.judge} (${d.reason.replaceAll("_", " ")})`)
                    .join("; ")}. Dropped quotes count nowhere.`
                : "Every quote in this conversation was found in its reply."}
            </p>
          </Card>
        </aside>
      </div>
      <Card title="Turn timeline">
        <TurnTimeline replies={data.replies} expected={data.expected} labels={data.labels} annotations={data.annotations} />
      </Card>
    </>
  );
}
