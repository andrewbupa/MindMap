import type { CSSProperties } from "react";

import type { AnnotationOut, ExpectationOut, EthosLabelOut, ReplyEthosOut } from "@/lib/api";

import { familyColour, formatMedian, INTENSITY, labelName } from "./family";

const MARKS = {
  match: ["✓", "found", "Expected and found"],
  miss: ["–", "missing", "Expected but missing"],
  intrusion: ["!", "intrusion", "Expected absent but found"],
  dispute: ["⚑", "dispute", "Judges differ by two points or more"],
} as const;

/** The labels a reply's strip shows: those the moment called for, and those found. */
export function stripLabels(reply: ReplyEthosOut, expected: ExpectationOut[], labels: EthosLabelOut[]): string[] {
  const shown = new Set([
    ...expected.filter((e) => e.expect !== "either").map((e) => e.label),
    ...reply.labels.filter((l) => l.median > 0).map((l) => l.label),
  ]);
  return labels.map((l) => l.key).filter((key) => shown.has(key));
}

function observedText(value: number): string {
  if (value % 1) return `Median ${formatMedian(value)}`;
  const word = INTENSITY[value] ?? String(value);
  return `${word.charAt(0).toUpperCase()}${word.slice(1)}, ${value}`;
}

function expectText(expect?: ExpectationOut): string {
  if (!expect || expect.expect === "either") return "Either";
  if (expect.expect === "absent") return "Expects none";
  return `Expects ${expect.min}${expect.max !== expect.min ? ` to ${expect.max}` : ""}`;
}

/**
 * One reply's profile: a cell per label with the panel's median as a filled channel, drawn
 * over a faint band for what the expected profile asked of the moment. Each name links to
 * the phrase that earned it.
 */
export function ProfileStrip({
  reply,
  expected,
  labels,
  annotations,
  onSelect,
}: {
  reply: ReplyEthosOut;
  expected: ExpectationOut[];
  labels: EthosLabelOut[];
  annotations: AnnotationOut[];
  onSelect: (label: string) => void;
}) {
  const families = new Map(labels.map((l) => [l.key, l.family]));
  const keys = stripLabels(reply, expected, labels);
  if (!keys.length) return null;
  const pc = (v: number) => `${(v / 3) * 100}%`;
  return (
    <ul className="ag-strip" aria-label="Profile of this reply against the expected profile">
      {keys.map((key) => {
        const found = reply.labels.find((l) => l.label === key);
        const median = found?.median ?? 0;
        const expect = expected.find((e) => e.label === key);
        const marks = [
          reply.fit?.matches.includes(key) ? MARKS.match : null,
          reply.fit?.misses.includes(key) ? MARKS.miss : null,
          reply.fit?.intrusions.includes(key) ? MARKS.intrusion : null,
          found?.disputed ? MARKS.dispute : null,
        ].filter((m) => m !== null);
        const band =
          expect?.expect === "present"
            ? expect.min === expect.max
              ? { left: `calc(${pc(expect.min)} - 7%)`, width: "14%" }
              : { left: pc(expect.min), width: `calc(${pc(expect.max)} - ${pc(expect.min)})` }
            : expect?.expect === "absent"
              ? { left: 0, width: "16%" }
              : null;
        const first = annotations.find(
          (a) => a.message_id === reply.message_id && a.label === key && a.channel === "content",
        );
        return (
          <li key={key} style={{ "--fam": familyColour(families.get(key) ?? "") } as CSSProperties}>
            <div className="ag-strip-head">
              <span className="ag-bead" aria-hidden="true" />
              <a
                className="ag-strip-name"
                href={first ? `#a-${first.id}` : `#r-${reply.message_id}`}
                onClick={() => onSelect(key)}
              >
                {labelName(key)}
              </a>
              {marks.map(([glyph, kind, words]) => (
                <span key={kind} className={`ag-mark ag-mark-${kind}`} title={words}>
                  <span aria-hidden="true">{glyph}</span>
                  <span className="ag-sr">{words}</span>
                </span>
              ))}
            </div>
            <div className="ag-strip-track ag-channel" aria-hidden="true">
              {band ? <span className="ag-strip-band" style={band} /> : null}
              {median > 0 ? <span className="ag-strip-fill" style={{ width: `calc(${pc(median)} - 4px)` }} /> : null}
              <span className="ag-strip-ticks">
                <i />
                <i />
                <i />
                <i />
              </span>
            </div>
            <div className="ag-strip-foot">
              <span>{observedText(median)}</span>
              <span>{expectText(expect)}</span>
            </div>
          </li>
        );
      })}
    </ul>
  );
}
