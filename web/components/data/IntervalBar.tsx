import type { CSSProperties } from "react";

/** A share and its 95% interval on a 0 to 100% track, in a family's hue when given. */
export function IntervalBar({
  value,
  low,
  high,
  label,
  family,
}: {
  /** Shares from 0 to 1. */
  value: number;
  low: number;
  high: number;
  label?: string;
  family?: string;
}) {
  const pc = (v: number) => `${Math.max(0, Math.min(100, v * 100))}%`;
  const whole = (v: number) => Math.round(v * 100);
  const words = `${label ? `${label}: ` : ""}${whole(value)}%, 95% interval ${whole(low)} to ${whole(high)}%`;
  const style = family ? ({ "--ag-ib": `var(--family-${family})` } as CSSProperties) : undefined;
  return (
    <div className="ag-ib" role="img" aria-label={words} style={style}>
      <div className="ag-ib-track ag-channel" aria-hidden="true">
        <span className="ag-ib-band" style={{ left: pc(low), width: `calc(${pc(high)} - ${pc(low)})` }} />
        <span className="ag-bead" style={{ left: pc(value) }} />
      </div>
      <span className="ag-ib-text" aria-hidden="true">
        {whole(value)}% <span>({whole(low)} to {whole(high)}%)</span>
      </span>
    </div>
  );
}
