"use client";

import Link from "next/link";
import { useState } from "react";

import { ScoreCell } from "@/components/data/ScoreCell";
import {
  ShortcutList,
  fieldKeys,
  focusOn,
  useShortcuts,
  useShortcutsOn,
  type Shortcut,
} from "@/components/jury/shortcuts";
import { Fold } from "@/components/runs/Messages";
import { Badge, Button, Card, EmptyState, Field, Notice, Radio, TextArea, sentenceCase } from "@/components/ui";
import { createReview, type ScoreReviewItem } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

type Verdict = "agree" | "disagree" | "unsure";
type Draft = { verdict: Verdict | null; corrected: string; notes: string };

const EMPTY: Draft = { verdict: null, corrected: "", notes: "" };
const VERDICTS: { value: Verdict; label: string; key: string }[] = [
  { value: "agree", label: "Agree", key: "a" },
  { value: "disagree", label: "Disagree", key: "d" },
  { value: "unsure", label: "Unsure", key: "u" },
];

const words = (value: string) => sentenceCase(value.replaceAll(/[-_]/g, " "));
const transcriptHref = (item: ScoreReviewItem) =>
  `/inquiry/transcripts/${item.transcript_id}#score-${item.score.dimension}`;

/**
 * Judge scores for an expert's verdict, one at a time, with every action on a key: move
 * with J and K, choose with A, D or U, give your own score with a number, and record with
 * Enter. Verdicts sit beside the judge's score; they never change it.
 */
export function ScoreQueue({ initial }: { initial: ScoreReviewItem[] }) {
  const [items, setItems] = useState(initial);
  const [at, setAt] = useState(0);
  const [drafts, setDrafts] = useState<Record<string, Draft>>({});
  const [error, setError] = useState<string | null>(null);
  const [status, setStatus] = useState("");
  const [busy, setBusy] = useState(false);
  const [on] = useShortcutsOn();

  const index = Math.min(at, items.length - 1);
  const item = items[index];
  const draft = (item && drafts[item.score.id]) ?? EMPTY;
  const max = item?.score.scale_max ?? 10;
  const corrected = Number(draft.corrected);
  const ready =
    draft.verdict !== null &&
    (draft.verdict !== "disagree" || draft.corrected === "" || (corrected >= 1 && corrected <= max));

  function update(change: Partial<Draft>) {
    if (!item) return;
    setDrafts((current) => ({
      ...current,
      [item.score.id]: { ...draft, ...change },
    }));
  }

  function move(to: number) {
    if (!items.length) return;
    setAt(Math.max(0, Math.min(items.length - 1, to)));
    setError(null);
    focusOn("jury-item");
  }

  async function record() {
    if (!item || !ready || busy) return;
    setBusy(true);
    setError(null);
    const { data, error: failed } = await createReview({
      client: browserClient,
      body: {
        score_id: item.score.id,
        verdict: draft.verdict!,
        corrected_value: draft.verdict === "disagree" && draft.corrected ? corrected : null,
        notes: draft.notes,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Your verdict was not saved. Try again.");
      return;
    }
    const left = items.length - 1;
    setItems((current) => current.filter((row) => row !== item));
    setStatus(left ? `Recorded. ${left} left.` : "Recorded. The queue is empty.");
    focusOn("jury-item");
  }

  const shortcuts: Shortcut[] = [
    { keys: ["j"], label: "Next item", run: () => move(index + 1) },
    { keys: ["k"], label: "Previous item", run: () => move(index - 1) },
    ...VERDICTS.map((v) => ({
      keys: [v.key],
      label: v.label,
      run: () => update({ verdict: v.value }),
    })),
    // Each number key gives your own score, so disagrees; 0 stands for 10.
    ...Array.from({ length: Math.min(max, 10) }, (_, i) => ({
      keys: [String((i + 1) % 10)],
      label: `Disagree, with your score${max >= 10 ? " (0 is 10)" : ""}`,
      display: max >= 10 ? "1 to 0" : `1 to ${max}`,
      run: () => update({ verdict: "disagree", corrected: String(i + 1) }),
    })),
    { keys: ["n"], label: "Write a note", run: () => focusOn("jury-notes") },
    {
      keys: ["o"],
      label: "Open the transcript",
      run: () => item && window.open(transcriptHref(item), "_blank"),
    },
    {
      keys: ["Enter"],
      label: "Record the verdict",
      run: () => void record(),
      disabled: !ready,
    },
  ];
  useShortcuts(on, shortcuts);

  if (!item) {
    return (
      <>
        <p role="status" className="ag-sr">
          {status}
        </p>
        <EmptyState title="Nothing is waiting for your review">
          New scores arrive here as Inquiry runs finish. The highest come first.
        </EmptyState>
      </>
    );
  }

  return (
    <div className="ag-split">
      <section aria-labelledby="jury-item">
        <Card>
          <p className="ag-quiet" style={{ marginTop: 0 }}>
            Item {index + 1} of {items.length}
          </p>
          <div className="ag-item-head">
            <h2 id="jury-item" tabIndex={-1}>
              {words(item.score.dimension)}
            </h2>
            <ScoreCell
              value={item.score.value}
              max={max}
              label={words(item.score.dimension)}
              href={transcriptHref(item)}
            />
          </div>
          <p>
            <Link href={transcriptHref(item)}>{words((item.scenario_key ?? "transcript").split("/").pop() ?? "transcript")}</Link> in{" "}
            <Link href={`/inquiry/runs/${item.run_id}`}>{item.run_title}</Link>.
          </p>
          <p className="ag-row" style={{ gap: "var(--space-2)" }}>
            {item.content_notes.map((note) => (
              <Badge key={note} tone="warn">
                Content note: {words(note).toLowerCase()}
              </Badge>
            ))}
            {item.reviews > 0 ? (
              <Badge>
                {item.reviews} other {item.reviews === 1 ? "review" : "reviews"}
              </Badge>
            ) : null}
          </p>
          {item.score.explanation ? (
            <Fold open summary="The judge’s reasons">
              {item.score.explanation}
            </Fold>
          ) : null}
          <div className="ag-form" style={{ marginTop: "var(--space-5)", maxWidth: "none" }}>
            {error ? <Notice tone="danger">{error}</Notice> : null}
            <fieldset className="ag-fieldset">
              <legend className="ag-label">Your verdict on this score</legend>
              <div className="ag-choices">
                {VERDICTS.map((v) => (
                  <Radio
                    key={v.value}
                    name={`verdict-${item.score.id}`}
                    label={v.label}
                    checked={draft.verdict === v.value}
                    onChange={() => update({ verdict: v.value })}
                  />
                ))}
              </div>
            </fieldset>
            {draft.verdict === "disagree" ? (
              <Field
                label={`Your score (1 to ${max})`}
                type="number"
                min={1}
                max={max}
                value={draft.corrected}
                onChange={(event) => update({ corrected: event.target.value })}
                onKeyDown={fieldKeys(record)}
                hint="Optional. Leave it empty to disagree without a number."
              />
            ) : null}
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
              <li key={row.score.id}>
                <button type="button" aria-current={i === index ? "true" : undefined} onClick={() => move(i)}>
                  <span>
                    {words(row.score.dimension)}: {row.score.value} of {row.score.scale_max}
                  </span>
                  <span className="ag-hint">
                    {words((row.scenario_key ?? "transcript").split("/").pop() ?? "transcript")}
                    {drafts[row.score.id]?.verdict ? `, ${drafts[row.score.id]!.verdict} in draft` : ""}
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
