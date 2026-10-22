"use client";

import { useState, type ReactNode } from "react";

import { cx } from "@/components/ui";

export type Column = { key: string; label: ReactNode; align?: "left" | "right"; sortable?: boolean };
export type Row = {
  id: string;
  cells: Record<string, ReactNode>;
  /** What each column sorts by; a column without one does not sort. */
  sort?: Record<string, number | string | null | undefined>;
};

/**
 * A table with a sticky header, two densities, and sorting on the columns that have sort
 * values. Rows arrive with their cells already made, so server pages can build them.
 */
export function DataTable({
  columns,
  rows,
  density = "comfortable",
  caption,
  initialSort,
  rowHeaders = false,
  maxHeight,
  empty,
}: {
  columns: Column[];
  rows: Row[];
  density?: "comfortable" | "dense";
  caption?: ReactNode;
  initialSort?: { key: string; dir: "asc" | "desc" };
  rowHeaders?: boolean;
  maxHeight?: number | string;
  empty?: ReactNode;
}) {
  const [sort, setSort] = useState(initialSort ?? null);
  const sortable = (key: string) =>
    columns.find((c) => c.key === key)?.sortable !== false && rows.some((r) => r.sort?.[key] !== undefined);
  const sorted = [...rows];
  if (sort) {
    sorted.sort((a, b) => {
      const x = a.sort?.[sort.key];
      const y = b.sort?.[sort.key];
      if (x === y) return 0;
      if (x === null || x === undefined) return 1;
      if (y === null || y === undefined) return -1;
      const diff = typeof x === "number" && typeof y === "number" ? x - y : String(x).localeCompare(String(y));
      return sort.dir === "asc" ? diff : -diff;
    });
  }

  function toggle(key: string) {
    setSort(sort && sort.key === key ? { key, dir: sort.dir === "asc" ? "desc" : "asc" } : { key, dir: "desc" });
  }

  return (
    <div className="ag-table-wrap" style={maxHeight ? { maxHeight } : undefined}>
      <table className={cx("ag-table", density === "dense" && "ag-table-dense")}>
        {caption ? <caption>{caption}</caption> : null}
        <thead>
          <tr>
            {columns.map((column) => {
              const can = sortable(column.key);
              const current = sort?.key === column.key ? (sort.dir === "asc" ? "ascending" : "descending") : "none";
              return (
                <th
                  key={column.key}
                  scope="col"
                  className={column.align === "right" ? "ag-right" : undefined}
                  aria-sort={can ? current : undefined}
                >
                  {can ? (
                    <button type="button" className="ag-sort" onClick={() => toggle(column.key)}>
                      {column.label}
                      <span className="ag-sort-glyph" aria-hidden="true" />
                    </button>
                  ) : (
                    column.label
                  )}
                </th>
              );
            })}
          </tr>
        </thead>
        <tbody>
          {sorted.map((row) => (
            <tr key={row.id}>
              {columns.map((column, index) => {
                const Cell = index === 0 && rowHeaders ? "th" : "td";
                return (
                  <Cell
                    key={column.key}
                    scope={index === 0 && rowHeaders ? "row" : undefined}
                    className={column.align === "right" ? "ag-right" : undefined}
                  >
                    {row.cells[column.key]}
                  </Cell>
                );
              })}
            </tr>
          ))}
          {rows.length === 0 && empty ? (
            <tr>
              <td colSpan={columns.length}>{empty}</td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}
