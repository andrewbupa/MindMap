import type { CSSProperties } from "react";

import type { AnnotationOut, ExpectationOut, EthosLabelOut, ReplyEthosOut } from "@/lib/api";

import { familyColour, intensityName } from "./family";
import { LabelChip } from "./LabelChip";

/**
 * How each label rises and settles across a conversation: a row per label, a column per
 * reply, a bead sized by the panel's median intensity, linked to the phrase behind it.
 */
export function TurnTimeline({
  replies,
  expected,
  labels,
  annotations,
}: {
  replies: ReplyEthosOut[];
  expected: ExpectationOut[];
  labels: EthosLabelOut[];
  annotations: AnnotationOut[];
}) {
  const present = new Set([
    ...replies.flatMap((r) => r.labels.filter((l) => l.median > 0).map((l) => l.label)),
    ...expected.filter((e) => e.expect === "present").map((e) => e.label),
  ]);
  const rows = labels.filter((l) => present.has(l.key));
  if (!rows.length || !replies.length) return <p>No labels were found in this conversation.</p>;
  return (
    <div className="ag-tl" role="table" aria-label="Labels across the conversation’s replies">
      <div role="row" className="ag-row">
        <span role="columnheader">
          <span className="ag-sr">Label</span>
        </span>
        <div className="ag-tl-cols" role="presentation">
          {replies.map((reply, index) => (
            <span key={reply.message_id} role="columnheader">
              <a href={`#r-${reply.message_id}`} aria-label={`Reply ${index + 1}`}>
                R{index + 1}
              </a>
            </span>
          ))}
        </div>
      </div>
      {rows.map((label) => (
        <div key={label.key} role="row" className="ag-row">
          <span role="rowheader">
            <LabelChip family={label.family} label={label.key} />
          </span>
          <div className="ag-tl-row" role="presentation" style={{ "--fam": familyColour(label.family) } as CSSProperties}>
            {replies.map((reply, index) => {
              const median = reply.labels.find((l) => l.label === label.key)?.median ?? 0;
              const first = annotations.find(
                (a) => a.message_id === reply.message_id && a.label === label.key && a.channel === "content",
              );
              const words = `Reply ${index + 1}: ${median > 0 ? intensityName(median) : "absent"}`;
              if (median <= 0 || !first) {
                return <span key={reply.message_id} className="ag-tl-zero" role="cell" aria-label={words} />;
              }
              const size = [0, 7, 11, 15][Math.round(median)] ?? 0;
              return (
                <span key={reply.message_id} role="cell">
                  <a href={`#a-${first.id}`} aria-label={words} style={{ display: "inline-flex" }}>
                    <span className="ag-bead" style={{ width: size, height: size }} />
                  </a>
                </span>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
