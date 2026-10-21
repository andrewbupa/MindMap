"use client";

import Link from "next/link";
import { useState } from "react";

import styles from "@/components/runs/runs.module.css";
import { Provenance } from "@/components/runs/Provenance";
import { Button, Card, Notice, PageHeader } from "@/components/ui";
import { finishConversation, say, type MessageOut, type PlaygroundOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

type ToolCall = { id: string; function: string; arguments: Record<string, unknown> };

function errorText(failed: unknown, fallback: string): string {
  const detail = (failed as { detail?: unknown } | undefined)?.detail;
  return typeof detail === "string" ? detail : fallback;
}

function MessageView({
  message,
  selected,
  onSelect,
}: {
  message: MessageOut;
  selected: boolean;
  onSelect: () => void;
}) {
  if (message.role === "system") {
    return (
      <details className={styles.system}>
        <summary>System prompt and context the agent received</summary>
        <pre>{message.content}</pre>
      </details>
    );
  }
  if (message.role === "tool") {
    return (
      <details className={styles.tool}>
        <summary>Tool result from a synthetic fixture</summary>
        <pre>{message.content}</pre>
      </details>
    );
  }
  const calls = (message.tool_calls ?? []) as ToolCall[];
  if (message.role === "assistant") {
    return (
      <div
        className={`${styles.bubble} ${styles.assistant} ${selected ? styles.selected : ""}`}
        onClick={onSelect}
        onKeyDown={(event) => (event.key === "Enter" ? onSelect() : undefined)}
        role="button"
        tabIndex={0}
        aria-pressed={selected}
      >
        <div className={styles.role}>Agent{message.thinking_summary ? " · has a thinking summary" : ""}</div>
        {message.content}
        {calls.map((call) => (
          <div key={call.id} className={styles.quiet}>
            Called {call.function}({JSON.stringify(call.arguments)})
          </div>
        ))}
      </div>
    );
  }
  return (
    <div className={`${styles.bubble} ${styles.user}`}>
      <div className={styles.role}>You</div>
      {message.content}
    </div>
  );
}

export function Conversation({ initial, canWrite }: { initial: PlaygroundOut; canWrite: boolean }) {
  const [run, setRun] = useState(initial.run);
  const [messages, setMessages] = useState(initial.messages);
  const [draft, setDraft] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const lastWithThinking = [...messages].reverse().find((m) => m.thinking_summary);
  const [selectedId, setSelectedId] = useState<string | null>(lastWithThinking?.id ?? null);
  const selected = messages.find((m) => m.id === selectedId);
  const live = run.status === "running";

  async function send() {
    if (!draft.trim()) return;
    setBusy(true);
    setError(null);
    const { data, error: failed } = await say({
      client: browserClient,
      path: { run_id: run.id },
      body: { content: draft },
    });
    setBusy(false);
    if (!data) {
      setError(errorText(failed, "The agent did not reply. Try again."));
      return;
    }
    setDraft("");
    setRun(data.run);
    setMessages((current) => [...current, ...data.messages]);
    const withThinking = [...data.messages].reverse().find((m) => m.thinking_summary);
    if (withThinking) setSelectedId(withThinking.id);
  }

  async function finish() {
    setBusy(true);
    const { data, error: failed } = await finishConversation({
      client: browserClient,
      path: { run_id: run.id },
    });
    setBusy(false);
    if (!data) {
      setError(errorText(failed, "The conversation could not be saved."));
      return;
    }
    setRun(data.run);
  }

  return (
    <>
      <PageHeader title={`Playground: ${initial.agent} ${initial.version}`}>
        <p>
          {initial.persona ? `Playing ${initial.persona.name}. ` : null}
          <Link href={`/agents/${initial.agent}`}>About this agent</Link>
        </p>
      </PageHeader>
      <div className={styles.layout}>
        <section aria-label="Conversation">
          <div className={styles.thread}>
            {messages.map((message) => (
              <MessageView
                key={message.id}
                message={message}
                selected={message.id === selectedId}
                onSelect={() => setSelectedId(message.id)}
              />
            ))}
          </div>
          {error ? <Notice tone="danger">{error}</Notice> : null}
          {run.status === "stopped_at_budget" ? (
            <Notice>This conversation reached its token budget and has been saved.</Notice>
          ) : null}
          {live && canWrite ? (
            <div className={styles.composer}>
              <label htmlFor="draft" className="visually-hidden">
                Your message
              </label>
              <textarea
                id="draft"
                value={draft}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) void send();
                }}
                placeholder="Write as the member would"
                disabled={busy}
              />
              <div className={styles.actions}>
                <Button onClick={send} disabled={busy || !draft.trim()}>
                  {busy ? "Waiting for the agent" : "Send"}
                </Button>
                <Button variant="secondary" onClick={finish} disabled={busy}>
                  Finish and save
                </Button>
              </div>
            </div>
          ) : null}
        </section>
        <aside className={styles.pane}>
          <Card title="Thinking summary">
            <p className={styles.quiet}>
              Written by a separate model. It summarises the agent&apos;s reasoning; it is not the
              reasoning itself.
            </p>
            {selected?.thinking_summary ? (
              <p className={styles.thinking}>{selected.thinking_summary}</p>
            ) : (
              <p className={styles.quiet}>Select an agent reply that has a summary.</p>
            )}
          </Card>
          <Card title="Run">
            <Provenance run={run} />
          </Card>
        </aside>
      </div>
    </>
  );
}
