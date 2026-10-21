import { Fragment } from "react";

import { familyColour, formatMedian, intensityName, labelName, tint } from "./family";
import styles from "./lens.module.css";

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
 * Where phrases overlap, the strongest shows; the others stay one click away. Every
 * finding has an anchor at its first character, so numbers elsewhere can link here.
 */
export function Highlighted({
  text,
  marks,
  selected,
  onSelect,
}: {
  text: string;
  marks: Mark[];
  selected?: string | null;
  onSelect?: (label: string) => void;
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
    <div className={styles.reply}>
      {points.slice(0, -1).map((from, index) => {
        const to = points[index + 1] ?? text.length;
        const covering = marks.filter((m) => m.start <= from && m.end >= to);
        const piece = text.slice(from, to);
        const ids = anchors.get(from) ?? [];
        const before = ids.map((id) => <span key={id} id={`a-${id}`} />);
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
        const title = names
          .map((name) => {
            const strongest = Math.max(...covering.filter((m) => m.label === name).map((m) => m.intensity));
            return `${labelName(name)}: ${intensityName(strongest)} (median ${formatMedian(strongest)})`;
          })
          .join("; ");
        return (
          <Fragment key={from}>
            {before}
            <button
              type="button"
              className={`${styles.mark} ${names.includes(selected ?? "") ? styles.selectedMark : ""}`}
              style={{ background: tint(top.family, top.intensity), borderBottomColor: familyColour(top.family) }}
              title={title}
              aria-label={`${piece}. ${title}`}
              onClick={() => onSelect?.(top.label)}
            >
              {piece}
            </button>
          </Fragment>
        );
      })}
    </div>
  );
}
