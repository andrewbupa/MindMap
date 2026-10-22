"use client";

import Link from "next/link";
import { useState } from "react";

import { ScoreCell } from "@/components/data/ScoreCell";
import { Badge, LinkButton, sentenceCase } from "@/components/ui";
import type { DimensionOut, TranscriptSummary } from "@/lib/api";

// Petri dimensions worth seeing beside ours before the rest are opened.
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

/** The design's heat: the series hue, up to 28% at the top of the scale. */
function heat(value: number, concern: boolean): string | undefined {
  if (!concern) return undefined;
  return `color-mix(in srgb, var(--color-chart-1) ${Math.round((Math.max(0, value) / 10) * 28)}%, transparent)`;
}

function seedName(transcript: TranscriptSummary): string {
  return sentenceCase((transcript.scenario_key ?? "seed").split("/").pop()!.replaceAll("-", " "));
}

/**
 * Judge dimensions by transcript, the most concerning first. Our dimensions lead; Petri's
 * built-in ones are folded away. Each cell links to the transcript and that score's reasons.
 */
export function Heatmap({
  transcripts,
  dimensions,
}: {
  transcripts: TranscriptSummary[];
  dimensions: DimensionOut[];
}) {
  const [all, setAll] = useState(false);
  const scored = new Set(transcripts.flatMap((t) => Object.keys(t.scores)));
  const ours = dimensions.filter((d) => d.custom && scored.has(d.name));
  const keyBuiltins = dimensions.filter((d) => !d.custom && scored.has(d.name) && KEY_BUILTINS.includes(d.name));
  const restBuiltins = dimensions.filter((d) => !d.custom && scored.has(d.name) && !KEY_BUILTINS.includes(d.name));
  const shown = [...ours, ...keyBuiltins, ...(all ? restBuiltins : [])];
  if (transcripts.length === 0) return <p>No transcripts have been scored yet.</p>;

  // Worst first: the highest score on our own dimensions, then on Petri's "concerning".
  const worst = (t: TranscriptSummary) =>
    Math.max(-1, ...ours.filter((d) => d.palette !== "good-high").map((d) => t.scores[d.name] ?? -1), t.scores.concerning ?? -1);
  const ordered = [...transcripts].sort((a, b) => worst(b) - worst(a));

  // Each seed's other repetitions, for the marks beside each score.
  const bySeed = new Map<string, TranscriptSummary[]>();
  for (const t of transcripts) bySeed.set(t.scenario_key ?? t.id, [...(bySeed.get(t.scenario_key ?? t.id) ?? []), t]);

  return (
    <div className="ag-table-wrap ag-heatmap">
      <table className="ag-table ag-table-dense">
        <caption className="ag-sr">Judge dimensions by transcript, most concerning first</caption>
        <thead>
          <tr>
            <th scope="col">Transcript</th>
            {shown.map((d) => (
              <th key={d.name} scope="col" title={d.description}>
                {d.display_name}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {ordered.map((t) => (
            <tr key={t.id}>
              <th
                scope="row"
                style={{ fontWeight: 400, color: "var(--color-text)", background: "var(--color-surface)", position: "static" }}
              >
                <Link href={`/inquiry/transcripts/${t.id}`}>{seedName(t)}</Link>
                {t.epoch > 1 ? ` (repetition ${t.epoch})` : ""}{" "}
                {t.content_notes.length ? <Badge tone="warn">Content note</Badge> : null}
              </th>
              {shown.map((d) => {
                const value = t.scores[d.name];
                const concern = d.palette !== "good-high";
                const samples = (bySeed.get(t.scenario_key ?? t.id) ?? [])
                  .map((other) => other.scores[d.name])
                  .filter((v): v is number => v !== undefined);
                return (
                  <td
                    key={d.name}
                    className="ag-heat"
                    style={value === undefined ? undefined : { background: heat(value, concern) }}
                  >
                    {value === undefined ? (
                      <span className="ag-muted">none</span>
                    ) : (
                      <ScoreCell
                        value={value}
                        samples={samples}
                        concern={concern}
                        label={d.display_name}
                        href={`/inquiry/transcripts/${t.id}#score-${d.name}`}
                      />
                    )}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
      <div className="ag-heat-foot">
        {restBuiltins.length ? (
          <LinkButton onClick={() => setAll(!all)} aria-expanded={all}>
            {all ? "Hide the other built-in dimensions" : `Show Petri’s other ${restBuiltins.length} built-in dimensions`}
          </LinkButton>
        ) : (
          <span />
        )}
        <span className="ag-heat-scale">
          0<span aria-hidden="true" />
          10, more concerning
        </span>
      </div>
    </div>
  );
}
