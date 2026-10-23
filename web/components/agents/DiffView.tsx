import type { ReactNode } from "react";

export type DiffLine = { n?: number | null; text?: string | null; change?: "added" | "removed" | null; note?: string };
export type DiffRow = { left: DiffLine; right: DiffLine };

const WORDS = { added: "Added: ", removed: "Removed: " };

/**
 * Two prompt versions side by side, changed lines marked with a sign and a tint as well as
 * colour. Rows share one grid, so a line that wraps on one side keeps the other level.
 */
export function DiffView({ left, right, rows }: { left: ReactNode; right: ReactNode; rows: DiffRow[] }) {
  const count = Math.max(1, rows.length);
  function column(title: ReactNode, side: "left" | "right") {
    return (
      <div className="ag-diff-col" style={{ gridRow: `1 / span ${count + 1}` }}>
        <div className="ag-diff-head">{title}</div>
        <ol style={{ gridRow: `span ${count}` }}>
          {rows.map((row, index) => {
            const line = row[side];
            const blank = line.text === null || line.text === undefined;
            return (
              <li key={index} className={line.change ? `is-${line.change}` : blank ? "is-blank" : undefined}>
                <span className="ag-diff-n">{line.n}</span>
                <span className="ag-diff-sign" aria-hidden="true">
                  {line.change === "removed" ? "−" : line.change === "added" ? "+" : ""}
                </span>
                <span>
                  {line.change ? <span className="ag-sr">{line.note ?? WORDS[line.change]}</span> : null}
                  {blank ? <span className="ag-sr">No line</span> : line.text}
                </span>
              </li>
            );
          })}
        </ol>
      </div>
    );
  }
  return (
    <div className="ag-diff" style={{ gridTemplateRows: `auto repeat(${count}, auto)` }}>
      {column(left, "left")}
      {column(right, "right")}
    </div>
  );
}
