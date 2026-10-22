"use client";

import Link from "next/link";
import { Fragment, useState, type CSSProperties, type ReactNode } from "react";

import { Card, Mono, Tabs } from "@/components/ui";
import type { WitnessSignalOut, WitnessTranscriptOut } from "@/lib/api";

import { labelName, SIGNAL_KINDS } from "./family";

export type ReplyText = { id: string; number: number; text: string };

/** A reply with each token shaded, in one silver hue, by one signal's value. */
function Shaded({ text, signal, top }: { text: string; signal: WitnessSignalOut; top: number }) {
  const pieces: ReactNode[] = [];
  let at = 0;
  for (const token of signal.tokens) {
    if (token.start > at) pieces.push(<Fragment key={`g${at}`}>{text.slice(at, token.start)}</Fragment>);
    const share = top > 0 ? Math.min(1, Math.max(0, token.value / top)) : 0;
    pieces.push(
      <span
        key={token.start}
        className="ag-sig"
        style={{ "--ag-sv": `${Math.round(share * 45)}%` } as CSSProperties}
        title={`${signal.name}: ${token.value.toFixed(2)}`}
      >
        {text.slice(token.start, token.end)}
      </span>,
    );
    at = token.end;
  }
  if (at < text.length) pieces.push(<Fragment key={`g${at}`}>{text.slice(at)}</Fragment>);
  return <p className="ag-signal-text">{pieces}</p>;
}

/**
 * Signals from an open-weight model reading this conversation, beside the panel's labels.
 * Shading follows one signal at a time; explanations quote the span they describe.
 */
export function WitnessPane({ data, replies, runHref }: { data: WitnessTranscriptOut; replies: ReplyText[]; runHref: string }) {
  const specs = data.reader.signals;
  const shaded = specs.filter((s) => s.kind !== "nla");
  const [chosen, setChosen] = useState(shaded[0]?.name ?? "");
  const spec = specs.find((s) => s.name === chosen);
  const ofChosen = data.signals.filter((s) => s.name === chosen);
  const top = Math.max(spec?.present_at ?? 0, ...ofChosen.map((s) => s.peak));
  const notes = data.signals.filter((s) => s.kind === "nla");
  const byId = new Map(replies.map((r) => [r.id, r]));

  return (
    <Card
      title="Open-model signals"
      actions={
        <span className="ag-sig-scale">
          Low
          <span aria-hidden="true" />
          High
        </span>
      }
    >
      <p className="ag-pane-def" style={{ margin: "0 0 var(--space-4)" }}>
        These signals are <Mono plain>{data.reader.model}</Mono>&rsquo;s reading of the text, not the agent&rsquo;s
        own internals. From <Link href={runHref}>{data.run.title}</Link>.
      </p>
      {shaded.length ? (
        <Tabs
          label="Signal to shade"
          value={chosen}
          onChange={setChosen}
          tabs={shaded.map((s) => ({ id: s.name, label: labelName(s.name) }))}
        />
      ) : null}
      {spec ? (
        <p className="ag-muted" style={{ fontSize: "var(--text-xs)", margin: "var(--space-3) 0 var(--space-2)" }}>
          {SIGNAL_KINDS[spec.kind] ?? spec.kind}. {spec.description}
          {spec.label ? ` Tracks ${labelName(spec.label).toLowerCase()}.` : ""}
          {spec.present_at !== null && spec.present_at !== undefined
            ? ` Counts as present at ${spec.present_at.toFixed(2)} or more.`
            : ""}
        </p>
      ) : null}
      {ofChosen.length === 0 && shaded.length ? <p>The reader returned no tokens for this signal.</p> : null}
      {ofChosen.map((signal) => {
        const reply = byId.get(signal.message_id);
        if (!reply) return null;
        return (
          <div key={signal.id} style={{ marginBottom: "var(--space-3)" }}>
            <a href={`#r-${signal.message_id}`}>
              Reply {reply.number}, peak {signal.peak.toFixed(2)}
            </a>
            <Shaded text={reply.text} signal={signal} top={top} />
          </div>
        );
      })}
      {notes.length ? (
        <div style={{ marginTop: "var(--space-5)" }}>
          <h3 style={{ margin: "0 0 var(--space-3)", fontSize: "var(--text-sm)", fontWeight: 600 }}>
            Autoencoder explanations
          </h3>
          <ul className="ag-expl">
            {notes.map((note) => {
              const reply = byId.get(note.message_id);
              if (!reply) return null;
              return (
                <li key={note.id}>
                  <q>{reply.text.slice(note.char_start, note.char_end)}</q>
                  <a href={`#r-${note.message_id}`}>Reply {reply.number}</a>: {note.explanation}
                </li>
              );
            })}
          </ul>
        </div>
      ) : null}
    </Card>
  );
}
