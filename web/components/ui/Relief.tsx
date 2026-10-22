"use client";

import { useId, type CSSProperties, type ReactElement } from "react";

import { cx } from "./format";

/*
 * The routed-ridge motif. Each route is a ridge: a crisp 1.25px crest, a lit flank tapering
 * away toward the top left, a shaded flank tapering toward the bottom right, and a fine
 * shaded lip under the crest. The flanks are stacks of strokes whose widths grow on a square
 * curve, so the profile peaks at the crest and tails off softly. Decorative, never animated.
 */
const ROUTES = {
  route: {
    viewBox: [0, 0, 480, 200],
    lit: 56,
    shade: 32,
    paths: [
      "M540 30H316A124 124 0 0 0 192 154V280",
      "M540 84H316A70 70 0 0 0 246 154V280",
      "M540 138H316A16 16 0 0 0 300 154V280",
      "M540 184H430A30 30 0 0 0 430 244H540",
    ],
  },
  hairpin: {
    viewBox: [0, 0, 480, 200],
    lit: 34,
    shade: 20,
    paths: ["M540 64H252A36 36 0 0 0 252 136H540", "M540 100H312"],
  },
} as const;

export type ReliefVariant = keyof typeof ROUTES;

export function Relief({
  variant = "route",
  width,
  height,
  preserve = "xMaxYMid slice",
  className,
  style,
  fade = true,
}: {
  variant?: ReliefVariant;
  width?: number | string;
  height?: number | string;
  preserve?: string;
  className?: string;
  style?: CSSProperties;
  fade?: boolean;
}) {
  const route = ROUTES[variant];
  const id = useId().replaceAll(":", "");
  const [, , vw, vh] = route.viewBox;

  function lanes(className: string | undefined, strokeWidth: number, key?: number, transform?: string) {
    return (
      <g
        key={key}
        className={className}
        fill="none"
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
        transform={transform}
      >
        {route.paths.map((d) => (
          <path key={d} d={d} />
        ))}
      </g>
    );
  }

  function flank(className: string, width: number, layers: number, dx: number, dy: number) {
    const strokes: ReactElement[] = [];
    for (let i = 1; i <= layers; i += 1) {
      strokes.push(lanes(undefined, Number((width * (i / layers) * (i / layers)).toFixed(2)), i));
    }
    return (
      <g className={className} filter={`url(#${id}-sm)`} transform={`translate(${dx} ${dy})`}>
        {strokes}
      </g>
    );
  }

  function fadeMask(name: string, x2: number, y2: number, stops: [number, string][]) {
    return (
      <>
        <linearGradient id={`${id}-${name}g`} gradientUnits="userSpaceOnUse" x1={0} y1={0} x2={x2} y2={y2}>
          {stops.map(([offset, colour]) => (
            <stop key={offset} offset={offset} stopColor={colour} />
          ))}
        </linearGradient>
        <mask id={`${id}-${name}`} maskUnits="userSpaceOnUse" x={-200} y={-200} width={vw + 400} height={vh + 400}>
          <rect x={-200} y={-200} width={vw + 400} height={vh + 400} fill={`url(#${id}-${name}g)`} />
        </mask>
      </>
    );
  }

  return (
    <svg
      className={cx("ag-relief", className)}
      viewBox={route.viewBox.join(" ")}
      width={width}
      height={height}
      preserveAspectRatio={preserve}
      aria-hidden="true"
      focusable="false"
      style={style}
    >
      <defs>
        <filter id={`${id}-sm`} x="-10%" y="-10%" width="120%" height="120%">
          <feGaussianBlur stdDeviation={1.2} />
        </filter>
        {fadeMask("fx", vw, 0, [[0, "#000"], [0.12, "#fff"], [0.86, "#fff"], [1, "#000"]])}
        {fadeMask("fy", 0, vh, [[0, "#000"], [0.1, "#fff"], [0.78, "#fff"], [1, "#000"]])}
      </defs>
      <g mask={fade ? `url(#${id}-fx)` : undefined}>
        <g mask={fade ? `url(#${id}-fy)` : undefined}>
          {flank("r-shade", route.shade, 10, 2, 2.5)}
          {flank("r-lit", route.lit, 20, -3, -3.5)}
          {lanes("r-lip", 1.4, undefined, "translate(0.8 0.9)")}
          {lanes("r-crest", 1.25)}
        </g>
      </g>
    </svg>
  );
}
