import type { AnnotationOut, ExpectationOut, LensLabelOut, ReplyLensOut } from "@/lib/api";

import { familyColour, formatMedian, intensityName, labelName, tint } from "./family";
import styles from "./lens.module.css";

type Verdict = "match" | "miss" | "intrusion" | null;

const MARKS: Record<Exclude<Verdict, null>, string> = { match: "✓", miss: "–", intrusion: "!" };
const WORDS: Record<Exclude<Verdict, null>, string> = {
  match: "expected and found",
  miss: "expected, not found",
  intrusion: "expected absent, found",
};

/** The labels a reply's strip shows: those the moment called for, and those found. */
export function stripLabels(
  reply: ReplyLensOut,
  expected: ExpectationOut[],
  labels: LensLabelOut[],
): string[] {
  const shown = new Set([
    ...expected.filter((e) => e.expect !== "either").map((e) => e.label),
    ...reply.labels.filter((l) => l.median > 0).map((l) => l.label),
  ]);
  return labels.map((l) => l.key).filter((key) => shown.has(key));
}

/**
 * One reply's profile: a bar per label for the panel's median intensity, drawn over a
 * faint band for what the expected profile asked of the moment. Each cell links to the
 * phrase that earned it.
 */
export function ProfileStrip({
  reply,
  expected,
  labels,
  annotations,
  onSelect,
}: {
  reply: ReplyLensOut;
  expected: ExpectationOut[];
  labels: LensLabelOut[];
  annotations: AnnotationOut[];
  onSelect: (label: string) => void;
}) {
  const families = new Map(labels.map((l) => [l.key, l.family]));
  const keys = stripLabels(reply, expected, labels);
  if (!keys.length) return null;
  return (
    <div className={styles.strip} aria-label="Profile of this reply">
      {keys.map((key) => {
        const found = reply.labels.find((l) => l.label === key);
        const median = found?.median ?? 0;
        const expect = expected.find((e) => e.label === key);
        const family = families.get(key) ?? "";
        let verdict: Verdict = null;
        if (reply.fit?.matches.includes(key)) verdict = "match";
        else if (reply.fit?.misses.includes(key)) verdict = "miss";
        else if (reply.fit?.intrusions.includes(key)) verdict = "intrusion";
        const first = annotations.find(
          (a) => a.message_id === reply.message_id && a.label === key && a.channel === "content",
        );
        const band =
          expect?.expect === "present"
            ? { bottom: `${(expect.min / 3) * 100}%`, top: `${100 - (expect.max / 3) * 100}%` }
            : expect?.expect === "absent"
              ? { bottom: "0%", top: "88%" }
              : null;
        const title = [
          `${labelName(key)}: ${intensityName(median)} (median ${formatMedian(median)})`,
          expect && expect.expect !== "either"
            ? expect.expect === "present"
              ? `expected ${intensityName(expect.min)} to ${intensityName(expect.max)}`
              : "expected absent"
            : null,
          verdict ? WORDS[verdict] : null,
          found?.disputed ? "judges differ by two or more" : null,
        ]
          .filter(Boolean)
          .join("; ");
        return (
          <a
            key={key}
            className={styles.cell}
            href={first ? `#a-${first.id}` : `#r-${reply.message_id}`}
            title={title}
            aria-label={title}
            onClick={() => onSelect(key)}
          >
            <span className={styles.track}>
              {band ? <span className={styles.band} style={band} /> : null}
              {median > 0 ? (
                <span
                  className={styles.bar}
                  style={{
                    height: `${(median / 3) * 100}%`,
                    background: tint(family, 3),
                    borderTop: `2px solid ${familyColour(family)}`,
                  }}
                />
              ) : null}
            </span>
            <span className={styles.cellLabel}>
              {verdict ? <span className={styles.verdict}>{MARKS[verdict]} </span> : null}
              {labelName(key)}
              {found?.disputed ? " ⚑" : ""}
            </span>
          </a>
        );
      })}
    </div>
  );
}
