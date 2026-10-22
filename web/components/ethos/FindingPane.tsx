import type { CSSProperties } from "react";

import { LinkButton, Mono } from "@/components/ui";
import type { AnnotationOut, ConsensusOut, EthosLabelOut } from "@/lib/api";

import { familyColour, formatMedian, intensityName } from "./family";
import { LabelChip, TrustBadge } from "./LabelChip";

function Dots({ value }: { value: number }) {
  return (
    <span className="ag-dots" aria-hidden="true">
      {[1, 2, 3].map((step) => (
        <i key={step} className={value >= step ? "on" : undefined} />
      ))}
    </span>
  );
}

/** One label in one reply: its definition and trust, the panel's median, and what each judge found. */
export function FindingPane({
  label,
  consensus,
  judges,
  annotations,
  onClose,
}: {
  label: EthosLabelOut;
  consensus?: ConsensusOut;
  judges: string[];
  /** This label's findings in this reply. */
  annotations: AnnotationOut[];
  onClose?: () => void;
}) {
  const median = consensus?.median ?? 0;
  return (
    <aside
      className="ag-card ag-pane"
      style={{ "--fam": familyColour(label.family) } as CSSProperties}
      aria-label={`Finding: ${label.key.replaceAll("_", " ")}`}
    >
      <div className="ag-pane-head">
        <LabelChip family={label.family} label={label.key} />
        <TrustBadge trust={label.trust_status} />
        {onClose ? (
          <span style={{ marginLeft: "auto" }}>
            <LinkButton onClick={onClose}>Close</LinkButton>
          </span>
        ) : null}
      </div>
      <p className="ag-pane-def">{label.definition}</p>
      <div className="ag-pane-median">
        <span className="ag-muted">Panel median</span>
        <b className="ag-num">{formatMedian(median)}</b>
        <span>{intensityName(median)}</span>
        {consensus?.disputed ? <span className="ag-mark ag-mark-dispute" title="Judges differ by two points or more">⚑ Judges differ by two or more</span> : null}
      </div>
      <ul className="ag-judges">
        {judges.map((judge) => {
          const intensity = consensus?.by_judge[judge] ?? 0;
          const quotes = annotations.filter((a) => a.judge === judge && a.channel === "content");
          return (
            <li key={judge} className="ag-judge">
              <div className="ag-judge-head">
                <Mono plain>{judge}</Mono>
                <span style={{ display: "inline-flex", gap: 8, alignItems: "center" }}>
                  <Dots value={intensity} />
                  <span className="ag-num">
                    {intensityName(intensity)} ({intensity})
                  </span>
                </span>
              </div>
              {quotes.map((quote) => (
                <div key={quote.id}>
                  <p className="ag-quote">
                    <a href={`#a-${quote.id}`}>&ldquo;{quote.quote}&rdquo;</a>
                  </p>
                  {quote.rationale ? <p className="ag-pane-def">{quote.rationale}</p> : null}
                </div>
              ))}
            </li>
          );
        })}
      </ul>
    </aside>
  );
}
