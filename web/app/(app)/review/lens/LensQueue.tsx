"use client";

import Link from "next/link";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { familyColour, intensityName, labelName } from "@/components/lens/family";
import lensStyles from "@/components/lens/lens.module.css";
import { Badge, Button, Card, Notice, sentenceCase } from "@/components/ui";
import { createReview, type LensDisputeOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const INTENSITIES = [0, 1, 2, 3];

function Verdict({ item, onDone }: { item: LensDisputeOut; onDone: () => void }) {
  const [intensity, setIntensity] = useState<number | null>(null);
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    if (intensity === null) return;
    setError(null);
    for (const annotation of item.annotations) {
      const { data, error: failed } = await createReview({
        client: browserClient,
        body: {
          annotation_id: annotation.id,
          verdict: annotation.intensity === intensity ? "agree" : "disagree",
          corrected_intensity: annotation.intensity === intensity ? null : intensity,
          notes,
        },
      });
      if (!data) {
        const detail = (failed as { detail?: unknown } | undefined)?.detail;
        setError(typeof detail === "string" ? detail : "Your verdict was not saved.");
        return;
      }
    }
    onDone();
  }

  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <fieldset className={styles.inlineForm} style={{ border: "none", padding: 0 }}>
        <legend>How strongly does this reply show {labelName(item.label).toLowerCase()}?</legend>
        {INTENSITIES.map((value) => (
          <label key={value}>
            <input
              type="radio"
              name={`intensity-${item.message_id}-${item.label}`}
              checked={intensity === value}
              onChange={() => setIntensity(value)}
            />{" "}
            {sentenceCase(intensityName(value))} ({value})
          </label>
        ))}
      </fieldset>
      <label className={styles.field}>
        Notes
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <p>
        <Button onClick={submit} disabled={intensity === null}>
          Record verdict
        </Button>
      </p>
    </div>
  );
}

export function LensQueue({ initial }: { initial: LensDisputeOut[] }) {
  const [items, setItems] = useState(initial);
  if (items.length === 0) return <Card>No Lens disagreements are waiting for you.</Card>;
  return (
    <>
      {items.map((item) => (
        <Card key={`${item.message_id}-${item.label}`}>
          <h3>
            <span className={lensStyles.swatch} style={{ background: familyColour(item.family) }} />
            {labelName(item.label)}
          </h3>
          <p>
            In{" "}
            <Link href={`/lens/runs/${item.lens_run_id}/transcripts/${item.transcript_id}#r-${item.message_id}`}>
              {sentenceCase((item.scenario_key ?? "a conversation").split("/").pop()!.replaceAll(/[-_]/g, " "))}
            </Link>{" "}
            from {item.lens_run_title}.{" "}
            {item.reviews > 0 ? <Badge>{item.reviews} reviews already</Badge> : null}
          </p>
          <blockquote className={lensStyles.thinking}>{item.reply_text}</blockquote>
          <table>
            <tbody>
              {Object.entries(item.by_judge).map(([judge, value]) => {
                const found = item.annotations.filter((a) => a.judge === judge);
                return (
                  <tr key={judge}>
                    <th scope="row">{judge}</th>
                    <td>
                      {sentenceCase(intensityName(value))} ({value})
                      {found.map((a) => (
                        <div key={a.id}>
                          &ldquo;{a.quote}&rdquo; <span className={lensStyles.quiet}>{a.rationale}</span>
                        </div>
                      ))}
                      {found.length === 0 ? <div className={lensStyles.quiet}>Found nothing.</div> : null}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          <Verdict item={item} onDone={() => setItems((current) => current.filter((row) => row !== item))} />
        </Card>
      ))}
    </>
  );
}
