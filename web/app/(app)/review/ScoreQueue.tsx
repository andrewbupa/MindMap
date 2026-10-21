"use client";

import Link from "next/link";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Badge, Button, Card, Notice, sentenceCase } from "@/components/ui";
import { createReview, type ScoreReviewItem } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

function ReviewForm({ item, onDone }: { item: ScoreReviewItem; onDone: () => void }) {
  const [verdict, setVerdict] = useState<"agree" | "disagree" | "unsure">("agree");
  const [corrected, setCorrected] = useState("");
  const [notes, setNotes] = useState("");
  const [error, setError] = useState<string | null>(null);

  async function submit() {
    setError(null);
    const { data, error: failed } = await createReview({
      client: browserClient,
      body: {
        score_id: item.score.id,
        verdict,
        corrected_value: verdict === "disagree" && corrected ? Number(corrected) : null,
        notes,
      },
    });
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Your review was not saved.");
      return;
    }
    onDone();
  }

  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <fieldset className={styles.inlineForm} style={{ border: "none", padding: 0 }}>
        <legend className="visually-hidden">Your verdict</legend>
        {(["agree", "disagree", "unsure"] as const).map((choice) => (
          <label key={choice}>
            <input
              type="radio"
              name={`verdict-${item.score.id}`}
              checked={verdict === choice}
              onChange={() => setVerdict(choice)}
            />{" "}
            {sentenceCase(choice)}
          </label>
        ))}
        {verdict === "disagree" ? (
          <label className={styles.field}>
            Your score (1 to 10)
            <input
              type="number"
              min={1}
              max={10}
              value={corrected}
              onChange={(event) => setCorrected(event.target.value)}
            />
          </label>
        ) : null}
      </fieldset>
      <label className={styles.field}>
        Notes
        <textarea value={notes} onChange={(event) => setNotes(event.target.value)} />
      </label>
      <p>
        <Button onClick={submit}>Record verdict</Button>
      </p>
    </div>
  );
}

export function ScoreQueue({ initial }: { initial: ScoreReviewItem[] }) {
  const [items, setItems] = useState(initial);
  if (items.length === 0) return <Card>Nothing is waiting for your review.</Card>;
  return (
    <>
      {items.map((item) => (
        <Card key={item.score.id}>
          <h3>
            {sentenceCase(item.score.dimension)}: {item.score.value} of {item.score.scale_max}
          </h3>
          <p>
            <Link href={`/explore/transcripts/${item.transcript_id}#score-${item.score.dimension}`}>
              {sentenceCase((item.scenario_key ?? "transcript").replaceAll("-", " "))}
            </Link>{" "}
            in <Link href={`/explore/runs/${item.run_id}`}>{item.run_title}</Link>{" "}
            {item.content_notes.map((note) => (
              <Badge key={note} tone="warn">
                Content note: {sentenceCase(note)}
              </Badge>
            ))}
            {item.reviews > 0 ? <Badge>{item.reviews} other reviews</Badge> : null}
          </p>
          {item.score.explanation ? (
            <details>
              <summary>The judge&apos;s reasons</summary>
              <p>{item.score.explanation}</p>
            </details>
          ) : null}
          <ReviewForm
            item={item}
            onDone={() => setItems((current) => current.filter((row) => row !== item))}
          />
        </Card>
      ))}
    </>
  );
}
