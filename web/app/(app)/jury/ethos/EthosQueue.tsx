"use client";

import Link from "next/link";
import { useState } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { INTENSITY, familyColour, formatMedian, intensityName, labelName } from "@/components/ethos/family";
import { Highlighted } from "@/components/ethos/Highlighted";
import { ShortcutList, fieldKeys, focusOn, useShortcuts, useShortcutsOn, type Shortcut } from "@/components/jury/shortcuts";
import { Badge, Bead, Button, Card, EmptyState, Notice, Radio, TextArea, sentenceCase } from "@/components/ui";
import { createReview, type EthosDisputeOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

type Draft = { intensity: number | null; notes: string };

const EMPTY: Draft = { intensity: null, notes: "" };

const idOf = (item: EthosDisputeOut) => `${item.message_id}:${item.label}`;
const scenarioName = (item: EthosDisputeOut) =>
  sentenceCase((item.scenario_key ?? "a conversation").split("/").pop()!.replaceAll(/[-_]/g, " "));
const replyHref = (item: EthosDisputeOut) =>
  `/ethos/runs/${item.ethos_run_id}/transcripts/${item.transcript_id}#r-${item.message_id}`;

/**
 * Replies where the Ethos judges differ by two points or more on a label, one at a time.
 * Move with J and K, give the intensity you would with 0 to 3, and record with Enter. Your
 * verdict is recorded against each judge's finding; it never changes them.
 */
export function EthosQueue({ initial }: { initial: EthosDisputeOut[] }) {
  const [items, setItems] = useState(initial);
  const [at, setAt] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [on] = useShortcutsOn();

  const index = Math.min(at, items.length - 1);
  const item = items[index];
  const draft = (item && drafts[idOf(item)]) ?? EMPTY;
  const ready = draft.intensity !== null;

  function update(change: Partial<Draft>) {
    if (!item) return;
    setDrafts((current) => ({ ...current, [idOf(item)]: { ...draft, ...change } }));
  }

  function move(to: number) {
    if (!items.length) return;
    setAt(Math.max(0, Math.min(items.length - 1, to)));
    setError(null);
    focusOn("jury-item");
  }

  async function record() {
    if (!item || draft.intensity === null || busy) return;
    const intensity = draft.intensity;
    setBusy(true);
    setError(null);
    for (const annotation of item.annotations) {
      const { data, error: failed } = await createReview({
        client: browserClient,
        body: {
          annotation_id: annotation.id,
          verdict: annotation.intensity === intensity ? "agree" : "disagree",
          corrected_intensity: annotation.intensity === intensity ? null : intensity,
          notes: draft.notes,
        },
      });
      if (!data) {
        setBusy(false);
        const detail = (failed as { detail?: unknown } | undefined)?.detail;
        setError(typeof detail === "string" ? detail : "Your verdict was not saved. Try again.");
        return;
      }
    }
    setBusy(false);
    const left = items.length - 1;
    setItems((current) => current.filter((row) => row !== item));
    setStatus(left ? `Recorded. ${left} left.` : "Recorded. The queue is empty.");
    focusOn("jury-item");
  }

  const shortcuts: Shortcut[] = [
    { keys: ["j"], label: "Next item", run: () => move(index + 1) },
    { keys: ["k"], label: "Previous item", run: () => move(index - 1) },
    ...INTENSITY.map((name, value) => ({
      keys: [String(value)],
      label: "The intensity you would give",
      display: "0 to 3",
      run: () => update({ intensity: value }),
    })),
    { keys: ["n"], label: "Write a note", run: () => focusOn("jury-notes") },
    { keys: ["o"], label: "Open the reply in Ethos", run: () => item && window.open(replyHref(item), "_blank") },
    { keys: ["Enter"], label: "Record the verdict", run: () => void record(), disabled: !ready },
  ];
  useShortcuts(on, shortcuts);

  if (!item) {
    return (
      <>
        <p role="status" className="ag-sr">
          {status}
        </p>
        <EmptyState title="No Ethos disagreements are waiting for you">
          A reply arrives here when the judges differ by two points or more on one of its labels.
        </EmptyState>
      </>
    );
  }

  const marks = item.annotations
    .filter((a) => a.channel === "content")
    .map((a) => ({ id: a.id, start: a.start, end: a.end, label: a.label, family: a.family, intensity: a.intensity }));
  const judges: Row[] = Object.entries(item.by_judge).map(([judge, value]) => {
    const found = item.annotations.filter((a) => a.judge === judge);
    return {
      id: judge,
      cells: {
        judge,
        intensity: (
          <span className="ag-num">
            {sentenceCase(intensityName(value))} ({value})
          </span>
        ),
        found: found.length ? (
          <div style={{ display: "grid", gap: "var(--space-2)" }}>
            {found.map((a) => (
              <div key={a.id}>
                <a href={`#a-${a.id}`}>&ldquo;{a.quote}&rdquo;</a> <span className="ag-muted">{a.rationale}</span>
              </div>
            ))}
          </div>
        ) : (
          <span className="ag-muted">Found nothing.</span>
        ),
      },
      sort: { judge, intensity: value },
    };
  });

  return (
    <div className="ag-split">
      <section aria-labelledby="jury-item">
        <Card>
          <p className="ag-quiet" style={{ marginTop: 0 }}>
            Item {index + 1} of {items.length}
          </p>
          <div className="ag-item-head">
            <h2 id="jury-item" tabIndex={-1}>
              {labelName(item.label)}
            </h2>
            <Badge icon={<Bead colour={familyColour(item.family)} />}>{sentenceCase(item.family)}</Badge>
            <Badge>Panel median {formatMedian(item.median)}</Badge>
            {item.reviews > 0 ? (
              <Badge>
                {item.reviews} {item.reviews === 1 ? "review" : "reviews"} already
              </Badge>
            ) : null}
          </div>
          <p>
            In <Link href={replyHref(item)}>{scenarioName(item)}</Link>, from {item.ethos_run_title}.
          </p>
          <div className="ag-msg-body ag-fold-body">
            <Highlighted text={item.reply_text} marks={marks} judges={Object.keys(item.by_judge).length} />
          </div>
          <h3 style={{ marginTop: "var(--space-5)" }}>What each judge found</h3>
          <DataTable
            density="dense"
            columns={[
              { key: "judge", label: "Judge" },
              { key: "intensity", label: "Intensity" },
              { key: "found", label: "Quotes and reasons", sortable: false },
            ]}
            rows={judges}
          />
          <div className="ag-form" style={{ marginTop: "var(--space-5)", maxWidth: "none" }}>
            {error ? <Notice tone="danger">{error}</Notice> : null}
            <fieldset className="ag-fieldset">
              <legend className="ag-label">
                How strongly does this reply show {labelName(item.label).toLowerCase()}?
              </legend>
              <div className="ag-choices">
                {INTENSITY.map((name, value) => (
                  <Radio
                    key={name}
                    name={`intensity-${idOf(item)}`}
                    label={`${sentenceCase(name)} (${value})`}
                    checked={draft.intensity === value}
                    onChange={() => update({ intensity: value })}
                  />
                ))}
              </div>
            </fieldset>
            <TextArea
              id="jury-notes"
              label="Notes"
              value={draft.notes}
              onChange={(event) => update({ notes: event.target.value })}
              onKeyDown={fieldKeys(record)}
              hint="Esc leaves the field; Ctrl or ⌘ with Enter records."
            />
            <div className="ag-row">
              <Button onClick={() => void record()} disabled={!ready || busy}>
                Record verdict
              </Button>
              <Button variant="secondary" onClick={() => move(index + 1)} disabled={index >= items.length - 1}>
                Skip for now
              </Button>
            </div>
          </div>
        </Card>
      </section>
      <aside aria-label="Queue and keys">
        <Card title={`Queue (${items.length})`}>
          <ol className="ag-queue">
            {items.map((row, i) => (
              <li key={idOf(row)}>
                <button type="button" aria-current={i === index ? "true" : undefined} onClick={() => move(i)}>
                  <span>{labelName(row.label)}</span>
                  <span className="ag-hint">
                    {scenarioName(row)}, judges {Object.values(row.by_judge).join(" and ")}
                    {drafts[idOf(row)]?.intensity !== undefined && drafts[idOf(row)]?.intensity !== null
                      ? `, ${INTENSITY[drafts[idOf(row)]!.intensity!]} in draft`
                      : ""}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </Card>
        <Card title="Keys">
          <ShortcutList shortcuts={shortcuts} />
        </Card>
      </aside>
      <p role="status" className="ag-sr">
        {status}
      </p>
    </div>
  );
}
