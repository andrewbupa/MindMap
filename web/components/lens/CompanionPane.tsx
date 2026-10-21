"use client";

import Link from "next/link";
import { Fragment, useState, type ReactNode } from "react";

import { Button, Card } from "@/components/ui";
import type { CompanionSignalOut, CompanionTranscriptOut } from "@/lib/api";

import { labelName } from "./family";
import styles from "./lens.module.css";

export type ReplyText = { id: string; number: number; text: string };

function strength(value: number, top: number): number {
  return top > 0 ? Math.min(1, Math.max(0, value / top)) : 0;
}

/** A reply with each token shaded by one signal's value. */
function Shaded({ text, signal, top }: { text: string; signal: CompanionSignalOut; top: number }) {
  const pieces: ReactNode[] = [];
  let at = 0;
  for (const token of signal.tokens) {
    if (token.start > at) pieces.push(<Fragment key={`g${at}`}>{text.slice(at, token.start)}</Fragment>);
    const share = strength(token.value, top);
    pieces.push(
      <span
        key={token.start}
        className={styles.token}
        style={{ background: `color-mix(in srgb, var(--color-chart-1) ${Math.round(share * 55)}%, transparent)` }}
        title={`${token.value.toFixed(2)}`}
      >
        {text.slice(token.start, token.end)}
      </span>,
    );
    at = token.end;
  }
  if (at < text.length) pieces.push(<Fragment key={`g${at}`}>{text.slice(at)}</Fragment>);
  return <div className={styles.signalText}>{pieces}</div>;
}

/**
 * Signals from an open-weight model reading this conversation, beside the panel's
 * labels. Shading follows one signal at a time; explanations quote their span.
 */
export function CompanionPane({
  data,
  replies,
  runHref,
}: {
  data: CompanionTranscriptOut;
  replies: ReplyText[];
  runHref: string;
}) {
  const specs = data.reader.signals;
  const shaded = specs.filter((s) => s.kind !== "nla");
  const [chosen, setChosen] = useState(shaded[0]?.name ?? "");
  const spec = specs.find((s) => s.name === chosen);
  const ofChosen = data.signals.filter((s) => s.name === chosen);
  const top = Math.max(spec?.present_at ?? 0, ...ofChosen.map((s) => s.peak));
  const notes = data.signals.filter((s) => s.kind === "nla");
  const byId = new Map(replies.map((r) => [r.id, r]));

  return (
    <Card title="Open-model signals">
      <p className={styles.quiet}>
        How {data.reader.model}, an open-weight model, reads this text (
        <Link href={runHref}>{data.run.title}</Link>). These are that model&apos;s signals, not the
        agent&apos;s own internals.
      </p>
      {shaded.length ? (
        <div className={styles.signalChoices} role="group" aria-label="Signal to shade">
          {shaded.map((s) => (
            <Button
              key={s.name}
              variant={s.name === chosen ? "primary" : "secondary"}
              aria-pressed={s.name === chosen}
              onClick={() => setChosen(s.name)}
            >
              {labelName(s.name)}
            </Button>
          ))}
        </div>
      ) : null}
      {spec ? (
        <p className={styles.quiet}>
          {spec.description}
          {spec.label ? ` Tracks ${labelName(spec.label).toLowerCase()}.` : ""}
          {spec.present_at !== null && spec.present_at !== undefined
            ? ` Counts as present at ${spec.present_at.toFixed(2)} or more.`
            : ""}
        </p>
      ) : null}
      {ofChosen.length === 0 && shaded.length ? <p>This reader returned no tokens for that signal.</p> : null}
      {ofChosen.map((signal) => {
        const reply = byId.get(signal.message_id);
        if (!reply) return null;
        return (
          <div key={signal.id} className={styles.signalReply}>
            <a href={`#r-${signal.message_id}`}>
              Reply {reply.number}, peak {signal.peak.toFixed(2)}
            </a>
            <Shaded text={reply.text} signal={signal} top={top} />
          </div>
        );
      })}
      {notes.length ? (
        <>
          <h3>Explanations</h3>
          {notes.map((note) => {
            const reply = byId.get(note.message_id);
            if (!reply) return null;
            return (
              <div key={note.id} className={styles.note}>
                <a href={`#r-${note.message_id}`}>
                  Reply {reply.number}: &ldquo;{reply.text.slice(note.char_start, note.char_end)}&rdquo;
                </a>
                <div className={styles.quiet}>{note.explanation}</div>
              </div>
            );
          })}
        </>
      ) : null}
    </Card>
  );
}
