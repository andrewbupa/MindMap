"use client";

import type { ReactNode } from "react";

import { Badge, Mono, cx } from "@/components/ui";
import type { MessageOut } from "@/lib/api";

type ToolCall = { id: string; function: string; arguments: Record<string, unknown> };
type Role = "system" | "member" | "agent" | "tool";

function roleOf(message: MessageOut): Role {
  if (message.role === "assistant") return "agent";
  if (message.role === "user") return "member";
  return message.role === "system" ? "system" : "tool";
}

export function Fold({
  summary,
  code = false,
  open,
  children,
}: {
  summary: ReactNode;
  code?: boolean;
  open?: boolean;
  children: ReactNode;
}) {
  return (
    <details className="ag-fold" open={open}>
      <summary>{summary}</summary>
      <div className={cx("ag-fold-body", code && "ag-code")}>{children}</div>
    </details>
  );
}

/**
 * The frame every message shares: a node on the conversation's route, a head with the
 * author, and the body. Each message has an anchor, #m-<index>, that evidence links to.
 */
export function MessageFrame({
  role,
  index,
  id,
  reference,
  author,
  authorNote,
  badges,
  selected = false,
  cited = false,
  children,
}: {
  role: Role;
  index: number;
  id?: string;
  /** The judge's own name for the message, such as M3, where it has one. */
  reference?: string | null;
  author: string;
  authorNote?: string;
  badges?: ReactNode;
  selected?: boolean;
  cited?: boolean;
  children: ReactNode;
}) {
  return (
    <article
      id={id ?? `m-${index}`}
      className={cx("ag-msg", `ag-msg-${role}`, selected && "ag-msg-selected", cited && "ag-msg-cited")}
    >
      <span className={cx("ag-msg-node", role === "agent" && "ag-bead")} aria-hidden="true" />
      <div className="ag-msg-head">
        {reference ? (
          <a className="ag-msg-ref" href={`#m-${index}`}>
            {reference}
          </a>
        ) : null}
        <span className="ag-msg-author">{author}</span>
        {authorNote ? <span className="ag-muted">{authorNote}</span> : null}
        {cited ? <Badge>Cited by the judge</Badge> : null}
        {badges}
      </div>
      {children}
    </article>
  );
}

/** One message in a transcript: system prompts and tool results fold away. */
export function MessageView({
  message,
  reference,
  selected = false,
  cited = false,
  onSelect,
  memberName,
}: {
  message: MessageOut;
  reference?: string | null;
  selected?: boolean;
  cited?: boolean;
  onSelect?: () => void;
  /** Who wrote the member's messages, when not the auditor: "You" in a rehearsal. */
  memberName?: string;
}) {
  const role = roleOf(message);
  const calls = (message.tool_calls ?? []) as ToolCall[];
  const badges = (
    <>
      {message.thinking_summary ? <Badge>Thinking summary</Badge> : null}
      {message.has_full_thinking ? <Badge tone="warn">Full thinking</Badge> : null}
    </>
  );
  const names = {
    system: "System prompt",
    tool: "Tool result",
    member: memberName ?? "Member",
    agent: "Agent",
  };
  const body =
    role === "system" ? (
      <Fold summary="Show the system prompt and context the agent received">{message.content}</Fold>
    ) : role === "tool" ? (
      <Fold summary="Show the result, from a synthetic fixture" code>
        {message.content}
      </Fold>
    ) : !message.content.trim() ? null : (
      <div
        className="ag-msg-body"
        onClick={onSelect}
        onKeyDown={(event) => (event.key === "Enter" && onSelect ? onSelect() : undefined)}
        role={onSelect ? "button" : undefined}
        tabIndex={onSelect ? 0 : undefined}
        aria-pressed={onSelect ? selected : undefined}
      >
        {message.content}
      </div>
    );
  return (
    <MessageFrame
      role={role}
      index={message.index}
      reference={reference}
      author={names[role]}
      authorNote={role === "member" && !memberName ? "played by the auditor" : undefined}
      badges={role === "agent" ? badges : null}
      selected={selected}
      cited={cited}
    >
      {body}
      {calls.length ? (
        <div className="ag-tools">
          {calls.map((call) => (
            <Fold
              key={call.id}
              code
              summary={
                <>
                  Called <Mono>{call.function}</Mono>
                </>
              }
            >
              {JSON.stringify(call.arguments, null, 2)}
            </Fold>
          ))}
        </div>
      ) : null}
    </MessageFrame>
  );
}
