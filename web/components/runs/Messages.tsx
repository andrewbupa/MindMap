"use client";

import type { MessageOut } from "@/lib/api";

import styles from "./runs.module.css";

type ToolCall = { id: string; function: string; arguments: Record<string, unknown> };

/** One message in a transcript. Each has an anchor, #m-<index>, that evidence can link to. */
export function MessageView({
  message,
  selected = false,
  cited = false,
  onSelect,
  speaker = "You",
}: {
  message: MessageOut;
  selected?: boolean;
  cited?: boolean;
  onSelect?: () => void;
  speaker?: string;
}) {
  const anchor = `m-${message.index}`;
  if (message.role === "system") {
    return (
      <details className={styles.system} id={anchor}>
        <summary>System prompt and context the agent received</summary>
        <pre>{message.content}</pre>
      </details>
    );
  }
  if (message.role === "tool") {
    return (
      <details className={styles.tool} id={anchor}>
        <summary>Tool result from a synthetic fixture</summary>
        <pre>{message.content}</pre>
      </details>
    );
  }
  const classes = [styles.bubble];
  if (message.role === "assistant") classes.push(styles.assistant!);
  else classes.push(styles.user!);
  if (selected) classes.push(styles.selected!);
  if (cited) classes.push(styles.cited!);
  const calls = (message.tool_calls ?? []) as ToolCall[];
  if (message.role === "assistant") {
    return (
      <div
        id={anchor}
        className={classes.join(" ")}
        onClick={onSelect}
        onKeyDown={(event) => (event.key === "Enter" && onSelect ? onSelect() : undefined)}
        role={onSelect ? "button" : undefined}
        tabIndex={onSelect ? 0 : undefined}
        aria-pressed={onSelect ? selected : undefined}
      >
        <div className={styles.role}>
          Agent{message.thinking_summary ? " · has a thinking summary" : ""}
          {message.has_full_thinking ? " · has full thinking (restricted)" : ""}
        </div>
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
    <div id={anchor} className={classes.join(" ")}>
      <div className={styles.role}>{speaker}</div>
      {message.content}
    </div>
  );
}
