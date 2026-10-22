import { Fragment, type CSSProperties, type KeyboardEvent } from "react";

import { familyColour, formatMedian, intensityName, intensityShare, labelName } from "./family";

export type Mark = {
  id: string;
  start: number;
  end: number;
  label: string;
  family: string;
  /** The panel's median intensity for this label in this reply. */
  intensity: number;
};

/**
 * Text with each quoted phrase tinted by its label's family, saturation for intensity.
 * Where phrases overlap, the strongest shows; the others are named on hover. Every finding
 * has an anchor at its first character, so numbers elsewhere can link here.
 */
export function Highlighted({
  text,
  marks,
  selected,
  onSelect,
  judges,
}: {
  text: string;
  marks: Mark[];
  selected?: string | null;
  onSelect?: (label: string) => void;
  judges?: number;
}) {
  const cuts = new Set([0, text.length]);
  for (const mark of marks) {
    cuts.add(mark.start);
    cuts.add(mark.end);
  }
  const points = [...cuts].sort((a, b) => a - b);
  const anchors = new Map<number, string[]>();
  for (const mark of marks) anchors.set(mark.start, [...(anchors.get(mark.start) ?? []), mark.id]);

  return (
    <div className="ag-msg-text">
      {points.slice(0, -1).map((from, index) => {
        const to = points[index + 1] ?? text.length;
        const covering = marks.filter((m) => m.start <= from && m.end >= to);
        const piece = text.slice(from, to);
        const before = (anchors.get(from) ?? []).map((id) => <span key={id} id={`a-${id}`} />);
        if (!covering.length) {
          return (
            <Fragment key={from}>
              {before}
              {piece}
            </Fragment>
          );
        }
        const top = covering.reduce((best, m) => (m.intensity > best.intensity ? m : best));
        const names = [...new Set(covering.map((m) => m.label))];
        const others = names.filter((name) => name !== top.label);
        const describe = `${labelName(top.label)}, ${intensityName(top.intensity)} (${formatMedian(top.intensity)}).`;
        const act = () => onSelect?.(top.label);
        return (
          <Fragment key={from}>
            {before}
            <span
              className="ag-hl"
              role="button"
              tabIndex={0}
              aria-pressed={names.includes(selected ?? "") ? true : undefined}
              aria-label={`${piece}. ${describe}${others.length ? ` Also ${others.map(labelName).join(", ")}.` : ""}`}
              style={{ "--fam": familyColour(top.family), "--ag-int": intensityShare(top.intensity) } as CSSProperties}
              onClick={act}
              onKeyDown={(event: KeyboardEvent<HTMLSpanElement>) => {
                if (event.key === "Enter" || event.key === " ") {
                  event.preventDefault();
                  act();
                }
              }}
            >
              {piece}
              <span className="ag-tip" role="tooltip">
                <b>{labelName(top.label)}</b>, {intensityName(top.intensity)} ({formatMedian(top.intensity)}).
                {judges ? ` Panel of ${judges} judges.` : ""}
                {others.length ? ` Also ${others.map(labelName).join(", ").toLowerCase()}.` : ""}
              </span>
            </span>
          </Fragment>
        );
      })}
    </div>
  );
}
