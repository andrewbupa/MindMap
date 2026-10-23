"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, type CSSProperties } from "react";

import { INTENSITY, familyColour, labelName } from "@/components/ethos/family";
import { ShortcutList, focusOn, useShortcuts, useShortcutsOn, type Shortcut } from "@/components/jury/shortcuts";
import { ContentNote } from "@/components/runs/ContentNote";
import { Fold, MessageFrame, MessageView } from "@/components/runs/Messages";
import { Button, Card, Notice, PageHeader, Radio, sentenceCase } from "@/components/ui";
import { saveGoldRatings, type GoldItemDetail } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const RATING = "data-rating";

/**
 * Blind labelling: the conversation and the labels, never the judges' findings or
 * another expert's ratings. Every label on every reply starts at absent. Tab moves from
 * label to label, the arrow keys or 0 to 3 rate the one in focus, and J and K move
 * between replies.
 */
export function LabelItem({ item }: { item: GoldItemDetail }) {
  const router = useRouter();
  const key = (message: string, label: string) => `${message}:${label}`;
  const [ratings, setRatings] = useState<Record<string, number>>(() =>
    Object.fromEntries(item.mine.map((r) => [key(r.message_id, r.label), r.intensity])),
  );
  const [saved, setSaved] = useState(item.mine.length > 0);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [on] = useShortcutsOn();
  const families = [...new Set(item.labels.map((l) => l.family))];
  const replies = new Set(item.replies);
  const rated = Object.values(ratings).filter((value) => value > 0).length;

  async function save() {
    if (busy) return;
    setBusy(true);
    setError(null);
    const body = item.replies.flatMap((message) =>
      item.labels.map((label) => ({
        message_id: message,
        label: label.key,
        intensity: ratings[key(message, label.key)] ?? 0,
      })),
    );
    const { data, error: failed } = await saveGoldRatings({
      client: browserClient,
      path: { set_id: item.gold_set, item_id: item.id },
      body: { ratings: body },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Your ratings were not saved. Try again.");
      return;
    }
    setSaved(true);
    if (item.next_item) router.push(`/jury/gold/${item.gold_set}/items/${item.next_item}`);
    else router.push(`/jury/gold/${item.gold_set}`);
  }

  /** The reply whose heading or labels hold focus, or -1. */
  function currentReply(): number {
    const within = document.activeElement?.closest("[data-reply]");
    return within ? item.replies.indexOf(within.getAttribute("data-reply") ?? "") : -1;
  }

  function rateFocused(value: number) {
    const target = document.activeElement;
    const name = target instanceof HTMLInputElement ? target.getAttribute(RATING) : null;
    if (!name) return;
    setRatings((current) => ({ ...current, [name]: value }));
    document.querySelector<HTMLInputElement>(`input[${RATING}="${name}"][value="${value}"]`)?.focus();
  }

  const shortcuts: Shortcut[] = [
    {
      keys: ["j"],
      label: "Next reply",
      run: () => focusOn(`reply-${item.replies[Math.min(item.replies.length - 1, currentReply() + 1)]}`),
    },
    {
      keys: ["k"],
      label: "Previous reply",
      run: () => focusOn(`reply-${item.replies[Math.max(0, currentReply() - 1)]}`),
    },
    ...INTENSITY.map((_, value) => ({
      keys: [String(value)],
      label: "Rate the label in focus",
      display: "0 to 3",
      run: () => rateFocused(value),
    })),
    { keys: ["s"], label: item.next_item ? "Save and label the next" : "Save", run: () => void save() },
  ];
  useShortcuts(on, shortcuts);

  return (
    <>
      <PageHeader
        title={`Label: ${sentenceCase((item.scenario_key ?? "transcript").split("/").pop()!.replaceAll(/[-_]/g, " "))}`}
      >
        <p>
          From <Link href={`/jury/gold/${item.gold_set}`}>{item.gold_set_name}</Link>. Rate how strongly each reply
          shows each label, on its own merits. Labels you leave at absent are saved as absent.
        </p>
      </PageHeader>
      {item.content_notes.map((note) => (
        <ContentNote key={note} topic={note} />
      ))}
      {saved ? <Notice>You have rated this transcript. Saving again replaces your ratings.</Notice> : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className="ag-split">
        <section aria-label="Conversation">
          {item.seed_text ? (
            <div style={{ marginBottom: "var(--space-4)" }}>
              <Fold summary="Show the scenario the conversation followed">{item.seed_text}</Fold>
            </div>
          ) : null}
          <div className="ag-route">
            {item.messages.map((message) => {
              if (!replies.has(message.id)) return <MessageView key={message.id} message={message} />;
              const number = item.replies.indexOf(message.id) + 1;
              return (
                <MessageFrame key={message.id} role="agent" index={message.index} author={`Agent, reply ${number}`}>
                  <div data-reply={message.id}>
                    <h2 id={`reply-${message.id}`} tabIndex={-1} className="ag-sr">
                      Reply {number}
                    </h2>
                    <div className="ag-msg-body">{message.content}</div>
                    <div className="ag-table-wrap" style={{ marginTop: "var(--space-3)" }}>
                      <table className="ag-table ag-table-dense ag-rating">
                        <caption className="ag-sr">Your ratings for reply {number}</caption>
                        <thead>
                          <tr>
                            <th scope="col">Label</th>
                            {INTENSITY.map((name, value) => (
                              <th key={name} scope="col" className="ag-center">
                                {sentenceCase(name)} <span className="ag-muted">{value}</span>
                              </th>
                            ))}
                          </tr>
                        </thead>
                        {families.map((family) => (
                          <tbody key={family}>
                            <tr>
                              <th
                                scope="rowgroup"
                                colSpan={5}
                                className="ag-rating-family"
                                style={{ "--fam": familyColour(family) } as CSSProperties}
                              >
                                {sentenceCase(family)}
                              </th>
                            </tr>
                            {item.labels
                              .filter((label) => label.family === family)
                              .map((label) => {
                                const name = key(message.id, label.key);
                                return (
                                  <tr key={label.key}>
                                    <th scope="row" title={label.definition}>
                                      {labelName(label.key)}
                                    </th>
                                    {INTENSITY.map((intensity, value) => (
                                      <td key={intensity} className="ag-center">
                                        <Radio
                                          label={<span className="ag-sr">{`${labelName(label.key)}: ${intensity}`}</span>}
                                          name={name}
                                          value={value}
                                          {...{ [RATING]: name }}
                                          checked={(ratings[name] ?? 0) === value}
                                          onChange={() => setRatings((current) => ({ ...current, [name]: value }))}
                                        />
                                      </td>
                                    ))}
                                  </tr>
                                );
                              })}
                          </tbody>
                        ))}
                      </table>
                    </div>
                  </div>
                </MessageFrame>
              );
            })}
          </div>
          <div style={{ marginTop: "var(--space-5)" }}>
            <Button onClick={() => void save()} disabled={busy}>
              {item.next_item ? "Save and label the next" : "Save"}
            </Button>
          </div>
        </section>
        <aside aria-label="Labels and keys">
          <Card title="Your ratings">
            <p className="ag-pane-def" style={{ margin: 0 }}>
              {rated === 0
                ? "Every label is at absent so far."
                : `${rated} ${rated === 1 ? "label is" : "labels are"} above absent.`}{" "}
              You never see the judges&apos; findings or another expert&apos;s ratings here.
            </p>
          </Card>
          <Card title="Labels">
            <div style={{ display: "grid", gap: "var(--space-2)" }}>
              {item.labels.map((label) => (
                <Fold key={label.key} summary={labelName(label.key)}>
                  {label.definition}
                </Fold>
              ))}
            </div>
          </Card>
          <Card title="Keys">
            <ShortcutList shortcuts={shortcuts} />
            <p className="ag-hint" style={{ marginBottom: 0 }}>
              Tab moves to the next label; the arrow keys also rate it.
            </p>
          </Card>
        </aside>
      </div>
    </>
  );
}
