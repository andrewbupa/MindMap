import type { CSSProperties } from "react";

import { familyColour, labelName } from "./family";

const FAMILIES: Record<string, string> = {
  care: "Care",
  collaboration: "Collaboration",
  judgement: "Judgement",
  curiosity: "Curiosity",
  risk: "Risk",
};
const TRUST: Record<string, string> = {
  trusted: "Trusted",
  provisional: "Provisional",
  retired: "Retired",
  unrated: "Unrated",
};

function TrustGlyph({ trust }: { trust: string }) {
  const common = { width: 10, height: 10, viewBox: "0 0 10 10", "aria-hidden": true };
  if (trust === "trusted")
    return (
      <svg {...common}>
        <circle cx={5} cy={5} r={4} fill="currentColor" />
      </svg>
    );
  if (trust === "provisional")
    return (
      <svg {...common}>
        <circle cx={5} cy={5} r={3.5} fill="none" stroke="currentColor" strokeWidth={1.2} />
        <path d="M5 1.5a3.5 3.5 0 0 1 0 7z" fill="currentColor" />
      </svg>
    );
  if (trust === "retired")
    return (
      <svg {...common}>
        <circle cx={5} cy={5} r={3.5} fill="none" stroke="currentColor" strokeWidth={1.2} />
        <path d="M2 8 8 2" stroke="currentColor" strokeWidth={1.2} />
      </svg>
    );
  return (
    <svg {...common}>
      <circle cx={5} cy={5} r={3.5} fill="none" stroke="currentColor" strokeWidth={1.2} strokeDasharray="1.6 1.6" />
    </svg>
  );
}

/** A label's trust, from the experts' agreement: a glyph and a word, never colour alone. */
export function TrustBadge({ trust, agreement }: { trust: string; agreement?: number | null }) {
  const known = TRUST[trust] ? trust : "unrated";
  const title =
    agreement !== null && agreement !== undefined
      ? `Agreement ${agreement.toFixed(2)}`
      : known === "unrated"
        ? "Too few expert ratings"
        : undefined;
  return (
    <span className={`ag-trust${known === "retired" ? " ag-trust-retired" : ""}`} title={title}>
      <TrustGlyph trust={known} />
      {TRUST[known]}
    </span>
  );
}

/** An Ethos label: its family's hue beside its name, and its trust when given. */
export function LabelChip({
  family,
  label,
  trust,
  agreement,
}: {
  family: string;
  label: string;
  trust?: string;
  agreement?: number | null;
}) {
  return (
    <span className="ag-chip" style={{ "--fam": familyColour(family) } as CSSProperties} title={FAMILIES[family]}>
      <span className="ag-bead" aria-hidden="true" />
      <span>{labelName(label)}</span>
      {trust ? <TrustBadge trust={trust} agreement={agreement} /> : null}
    </span>
  );
}
