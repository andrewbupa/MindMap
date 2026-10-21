"use client";

import Link from "next/link";
import { useState } from "react";

import styles from "@/components/runs/runs.module.css";
import { Badge, LinkButton, sentenceCase } from "@/components/ui";
import type { DimensionOut, TranscriptSummary } from "@/lib/api";

// Petri dimensions worth seeing beside ours by default.
const KEY_BUILTINS = [
  "concerning",
  "needs_attention",
  "disappointing",
  "user_over_sysprompt",
  "unprompted_sycophancy",
  "overrefusal",
  "admirable",
  "scenario_realism",
];

function tint(value: number, palette: string): string {
  const strength = Math.round(((value - 1) / 9) * 70);
  const hue =
    palette === "good-high"
      ? "var(--color-ok)"
      : palette === "good-low"
        ? "var(--color-danger)"
        : "var(--color-accent)";
  return `color-mix(in srgb, ${hue} ${strength}%, var(--color-surface))`;
}

/** Scores by transcript and dimension. Each cell links to the transcript and its score. */
export function Heatmap({
  transcripts,
  dimensions,
}: {
  transcripts: TranscriptSummary[];
  dimensions: DimensionOut[];
}) {
  const [all, setAll] = useState(false);
  const scored = new Set(transcripts.flatMap((t) => Object.keys(t.scores)));
  const shown = dimensions.filter(
    (d) => scored.has(d.name) && (all || d.custom || KEY_BUILTINS.includes(d.name)),
  );
  if (transcripts.length === 0) return <p>No transcripts have been scored yet.</p>;

  return (
    <div className={styles.heatmap}>
      <table>
        <thead>
          <tr>
            <th scope="col">Seed</th>
            {shown.map((d) => (
              <th key={d.name} scope="col" className={styles.column} title={d.description}>
                {d.display_name}
                {d.custom ? " ★" : ""}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {transcripts.map((t) => (
            <tr key={t.id}>
              <th scope="row">
                <Link href={`/explore/transcripts/${t.id}`}>
                  {sentenceCase((t.scenario_key ?? "seed").replaceAll("-", " "))}
                </Link>
                {t.epoch > 1 ? ` (${t.epoch})` : ""}{" "}
                {t.content_notes.length ? <Badge tone="warn">Content note</Badge> : null}
              </th>
              {shown.map((d) => {
                const value = t.scores[d.name];
                return (
                  <td key={d.name}>
                    {value === undefined ? null : (
                      <Link
                        className={styles.cell}
                        style={{ background: tint(value, d.palette) }}
                        href={`/explore/transcripts/${t.id}#score-${d.name}`}
                        title={`${d.display_name}: ${value} of 10. Open the transcript and the judge's reasons.`}
                      >
                        {value}
                      </Link>
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className={styles.legend}>
        <span>Scores run from 1 to 10.</span>
        <span>Red: higher is worse.</span>
        <span>Green: higher is better.</span>
        <span>Our dimensions come first.</span>
        <LinkButton onClick={() => setAll(!all)}>
          {all ? "Show key dimensions only" : `Show all ${scored.size} dimensions`}
        </LinkButton>
      </div>
    </div>
  );
}
