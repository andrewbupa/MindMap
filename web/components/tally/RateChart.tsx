import type { ElicitationOut } from "@/lib/api";

export type RatePoint = { label: string; href: string; elicitation: ElicitationOut };

const W = 560;
const H = 248;
const L = 48;
const R = 28;
const T = 34;
const B = 40;

const pct = (share: number | null | undefined) => (share === null || share === undefined ? null : Math.round(share * 100));

/**
 * Elicitation rate by prompt version: the rate over every repetition with its spread across
 * repetitions, joined along a route. A version worse than the one before turns red and says
 * by how much. Each version links to its run; the table that follows has the same numbers.
 */
export function RateChart({ points }: { points: RatePoint[] }) {
  const data = points.map((point) => {
    const rate = pct(point.elicitation.overall.rate) ?? 0;
    const reps = point.elicitation.by_epoch.map((e) => pct(e.rate)).filter((r): r is number => r !== null);
    return {
      ...point,
      rate,
      reps,
      low: pct(point.elicitation.spread_low) ?? rate,
      high: pct(point.elicitation.spread_high) ?? rate,
    };
  });
  const top = Math.max(1, ...data.map((d) => d.high));
  const step = [5, 10, 20, 25].find((s) => s * 4 >= top * 1.15) ?? 25;
  const ymax = step * 4;
  const pw = W - L - R;
  const ph = H - T - B;
  const x = (i: number) => L + ((i + 0.5) * pw) / (data.length || 1);
  const y = (v: number) => T + ph - (v / ymax) * ph;
  const ticks = [0, 1, 2, 3, 4].map((k) => (k * ymax) / 4);
  const worse = data.map((d, i) => i > 0 && d.rate > data[i - 1]!.rate);
  const route = data.map((d, i) => `${i ? "L" : "M"}${x(i)} ${y(d.rate)}`).join(" ");
  const summary =
    "Elicitation rate by prompt version: " +
    data.map((d) => `${d.label} ${d.rate}% (${d.low} to ${d.high}% across repetitions)`).join(", ") +
    ".";

  return (
    <div className="ag-chart-wrap">
      <svg className="ag-chart" viewBox={`0 0 ${W} ${H}`} role="img" aria-label={summary}>
        {ticks.map((tick) => (
          <g key={tick}>
            <line className="c-grid" x1={L} x2={W - R} y1={y(tick)} y2={y(tick)} />
            <text className="c-axis" x={L - 10} y={y(tick) + 4} textAnchor="end">
              {tick}%
            </text>
          </g>
        ))}
        <path className="c-route-bed" d={route} />
        <path className="c-route" d={route} />
        {data.map((d, i) => {
          const cx = x(i);
          const previous = data[i - 1];
          return (
            <a key={d.href} href={d.href} aria-label={`${d.label}: ${d.rate}%. Open the run.`}>
              <g className={worse[i] ? "c-worse" : undefined}>
                <line className="c-whisker" x1={cx} x2={cx} y1={y(d.low)} y2={y(d.high)} />
                <line className="c-whisker" x1={cx - 6} x2={cx + 6} y1={y(d.low)} y2={y(d.low)} />
                <line className="c-whisker" x1={cx - 6} x2={cx + 6} y1={y(d.high)} y2={y(d.high)} />
                {d.reps.map((rep, j) => (
                  <circle key={j} className="c-rep" cx={cx + 16 + j * 7} cy={y(rep)} r={3} />
                ))}
                {worse[i] ? <circle className="c-ring" cx={cx} cy={y(d.rate)} r={12} /> : null}
                <circle className="c-mean" cx={cx} cy={y(d.rate)} r={6.5} />
                <text className="c-val" x={cx - 14} y={y(d.rate) + 4} textAnchor="end">
                  {d.rate}%
                </text>
                {worse[i] && previous ? (
                  <text
                    className="c-note"
                    x={i === data.length - 1 ? cx + 28 : cx}
                    y={Math.max(14, y(d.high) - 14)}
                    textAnchor={i === data.length - 1 ? "end" : "middle"}
                  >
                    Worse than {previous.label} by {d.rate - previous.rate} points
                  </text>
                ) : null}
                <text className="c-ver" x={cx} y={H - 14} textAnchor="middle">
                  {d.label}
                </text>
              </g>
            </a>
          );
        })}
      </svg>
    </div>
  );
}
