import Link from "next/link";

/**
 * A score with a small mark of where it sits on the scale, beside the other samples of the
 * same seed. A concerning score's bead turns red. Links to the evidence.
 */
export function ScoreCell({
  value,
  max = 10,
  samples = [],
  href,
  label,
  threshold = 7,
  concern = true,
}: {
  value: number;
  max?: number;
  samples?: number[];
  href?: string;
  label?: string;
  threshold?: number;
  /** False where a higher score is better, so it never reads as a concern. */
  concern?: boolean;
}) {
  const at = (x: number) => `${(Math.max(0, Math.min(max, x)) / max) * 100}%`;
  const worrying = concern && value >= threshold;
  const inner = (
    <>
      <span className="ag-score-num">{value}</span>
      <span className="ag-score-of">of {max}</span>
      <span className="ag-score-track ag-channel" aria-hidden="true">
        {samples.map((sample, index) => (
          <i key={index} style={{ left: at(sample) }} />
        ))}
        <span
          className="ag-bead"
          style={{ left: at(value), ["--ag-bead" as string]: worrying ? "var(--color-danger)" : "var(--color-chart-1)" }}
        />
      </span>
    </>
  );
  const words =
    (label ? `${label}: ` : "") +
    `${value} of ${max}` +
    (samples.length > 1 ? `, across ${samples.length} samples of this seed` : "");
  return href ? (
    <Link className="ag-score" href={href} aria-label={words}>
      {inner}
    </Link>
  ) : (
    <span className="ag-score" role="img" aria-label={words}>
      {inner}
    </span>
  );
}
