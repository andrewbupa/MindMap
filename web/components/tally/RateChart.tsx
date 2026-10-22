"use client";

import { useState } from "react";

import type { ElicitationOut } from "@/lib/api";

import { meanText, percent, spreadText, tallyText } from "./format";
import styles from "./tally.module.css";

export type RatePoint = { label: string; href: string; elicitation: ElicitationOut };

const PLOT = { top: 24, bottom: 44, left: 44, right: 16, height: 200 };
const BAND = 120;
const COLUMN = 24;
const TICKS = [0, 0.25, 0.5, 0.75, 1];

/** A rounded data-end on top, square at the baseline. */
function columnPath(x: number, y: number, base: number): string {
  const r = Math.min(4, base - y);
  return `M${x},${base} L${x},${y + r} Q${x},${y} ${x + r},${y} L${x + COLUMN - r},${y} Q${x + COLUMN},${y} ${x + COLUMN},${y + r} L${x + COLUMN},${base} Z`;
}

/** Beside the hovered column, on the side with room, level with the column's top. */
function tooltipPosition(index: number, count: number, width: number, height: number, top: number) {
  const centre = PLOT.left + BAND * index + BAND / 2;
  const flip = index === count - 1 && count > 1;
  return {
    left: `${((flip ? centre - BAND / 2 : centre + BAND / 2) / width) * 100}%`,
    top: `${(Math.min(top, height - PLOT.bottom - 60) / height) * 100}%`,
    transform: flip ? "translate(-100%, -50%)" : "translate(0, -50%)",
  };
}

/**
 * Elicitation rate by prompt version: a column for the rate over every repetition,
 * and beside it a dot for each repetition joined by its range. Every column links to
 * its run; the table that follows carries the same numbers.
 */
export function RateChart({ points }: { points: RatePoint[] }) {
  const [active, setActive] = useState<number | null>(null);
  const width = PLOT.left + PLOT.right + Math.max(points.length, 3) * BAND;
  const height = PLOT.top + PLOT.height + PLOT.bottom;
  const base = PLOT.top + PLOT.height;
  const y = (rate: number) => PLOT.top + PLOT.height * (1 - rate);
  const left = (index: number) => PLOT.left + BAND * index + (BAND - COLUMN) / 2 - 10;

  const shown = active === null ? null : points[active];
  return (
    <div className={styles.chart}>
      <svg
        width={width}
        height={height}
        viewBox={`0 0 ${width} ${height}`}
        role="img"
        aria-label="Elicitation rate by prompt version. The table below gives the same numbers."
      >
        {TICKS.map((tick) => (
          <g key={tick}>
            <line className={styles.grid} x1={PLOT.left} x2={width - PLOT.right} y1={y(tick)} y2={y(tick)} />
            <text className={styles.axis} x={PLOT.left - 8} y={y(tick) + 4} textAnchor="end">
              {tick * 100}%
            </text>
          </g>
        ))}
        {points.map((point, index) => {
          const { overall, by_epoch: epochs } = point.elicitation;
          const x = left(index);
          const dotX = x + COLUMN + 12;
          const rates = epochs.map((e) => e.rate).filter((r): r is number => r !== null && r !== undefined);
          const rate = overall.rate;
          return (
            <a
              key={point.href}
              href={point.href}
              className={styles.group}
              aria-label={`${point.label}: ${percent(rate)}, ${tallyText(overall)}. Repetitions: ${spreadText(point.elicitation)}.`}
              onPointerEnter={() => setActive(index)}
              onPointerLeave={() => setActive(null)}
              onFocus={() => setActive(index)}
              onBlur={() => setActive(null)}
            >
              <rect
                className={styles.hit}
                x={PLOT.left + BAND * index + 2}
                y={PLOT.top - 20}
                width={BAND - 4}
                height={PLOT.height + 20}
                rx={4}
              />
              {rate !== null && rate !== undefined && rate > 0 ? (
                <path className={styles.column} d={columnPath(x, y(rate), base)} />
              ) : null}
              {rates.length > 1 ? (
                <line
                  className={styles.range}
                  x1={dotX}
                  x2={dotX}
                  y1={y(Math.max(...rates))}
                  y2={y(Math.min(...rates))}
                />
              ) : null}
              {rates.map((value, at) => (
                <circle key={at} className={styles.dot} cx={dotX} cy={y(value)} r={4} />
              ))}
              <text className={styles.label} x={x + COLUMN / 2} y={y(rate ?? 0) - 8} textAnchor="middle">
                {percent(rate)}
              </text>
              <text className={styles.label} x={x + COLUMN / 2 + 6} y={base + 18} textAnchor="middle">
                {point.label}
              </text>
              <text className={styles.axis} x={x + COLUMN / 2 + 6} y={base + 34} textAnchor="middle">
                {overall.rollouts} scored
              </text>
            </a>
          );
        })}
      </svg>
      {shown && active !== null ? (
        <div
          className={styles.tooltip}
          style={tooltipPosition(active, points.length, width, height, y(shown.elicitation.overall.rate ?? 0))}
        >
          <strong>{percent(shown.elicitation.overall.rate)}</strong> {shown.label}
          <div>{tallyText(shown.elicitation.overall)} scored 7 or more</div>
          <div>Repetitions: {spreadText(shown.elicitation)}</div>
          <div>Mean presence: {meanText(shown.elicitation.overall)}</div>
        </div>
      ) : null}
      <div className={styles.key}>
        <span>
          <span className={styles.swatch} />
          Rate over every repetition
        </span>
        <span>
          <span className={styles.keyDot} />
          One repetition; the line spans lowest to highest
        </span>
      </div>
    </div>
  );
}
