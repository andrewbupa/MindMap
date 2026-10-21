"use client";

import { useState } from "react";

import { Button, Card, Notice } from "@/components/ui";
import { readFullThinking, type FullThinkingOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

import styles from "./runs.module.css";

/** Full thinking, for the rare runs Anthropic returns it. Kept apart from thinking
 * summaries, fetched on request, and only for admins and compliance. */
export function FullThinking({ transcriptId, allowed }: { transcriptId: string; allowed: boolean }) {
  const [items, setItems] = useState<FullThinkingOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function open() {
    setError(null);
    const { data, error: failure } = await readFullThinking({
      client: browserClient,
      path: { transcript_id: transcriptId },
    });
    if (data) setItems(data);
    else {
      const detail = (failure as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The full thinking could not be opened.");
    }
  }

  return (
    <Card title="Full thinking (restricted)">
      <p className={styles.quiet}>
        The model&apos;s own reasoning, which Anthropic returns only by special arrangement. It is
        not a summary. Only admins and compliance can read it, and each reading is recorded in the
        audit log.
      </p>
      {!allowed ? (
        <p>This transcript holds full thinking. Ask an admin or compliance if you need it.</p>
      ) : items === null ? (
        <Button onClick={open}>Read the full thinking</Button>
      ) : (
        items.map((item) => (
          <section key={item.message_id}>
            <h3>
              <a href={`#m-${item.index}`}>Reply at message {item.index + 1}</a>
            </h3>
            <p className={styles.thinking}>{item.thinking_full}</p>
          </section>
        ))
      )}
      {error ? <Notice tone="danger">{error}</Notice> : null}
    </Card>
  );
}
