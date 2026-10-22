"use client";

import { useState } from "react";

import { Notice } from "@/components/ui";
import { readFullThinking, type FullThinkingOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

/** Full thinking, for the rare runs Anthropic returns it. Kept apart from thinking
 * summaries, fetched when opened, and only for admins and compliance. */
export function FullThinking({ transcriptId, allowed }: { transcriptId: string; allowed: boolean }) {
  const [items, setItems] = useState<FullThinkingOut[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  if (!allowed) {
    return (
      <Notice title="Full thinking (restricted)">
        This transcript holds full thinking. Only admins and compliance can read it.
      </Notice>
    );
  }

  async function open() {
    if (items) return;
    setError(null);
    const { data, error: failure } = await readFullThinking({
      client: browserClient,
      path: { transcript_id: transcriptId },
    });
    if (data) setItems(data);
    else {
      const detail = (failure as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The full thinking could not be opened. Try again.");
    }
  }

  return (
    <details
      className="ag-fold ag-thinking"
      onToggle={(event) => {
        if ((event.target as HTMLDetailsElement).open) void open();
      }}
    >
      <summary>Full thinking (restricted)</summary>
      <p className="ag-thinking-note">
        The model&apos;s own reasoning, not a summary. Admins and compliance only. Each reading is
        recorded in the audit log, and full thinking is never shown beside summaries.
      </p>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {(items ?? []).map((item) => (
        <div key={item.message_id} className="ag-fold-body">
          <a href={`#m-${item.index}`}>Reply at message {item.index + 1}</a>
          {"\n"}
          {item.thinking_full}
        </div>
      ))}
    </details>
  );
}
