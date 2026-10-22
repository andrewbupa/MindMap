import Link from "next/link";
import type { ReactNode } from "react";

import { DataTable, type Column, type Row } from "@/components/data/DataTable";
import { formatNumber, formatWhen } from "@/components/ui";
import type { RunOut } from "@/lib/api";

import { StatusBadge } from "./StatusBadge";

/** Runs in a sortable table: each title opens its run, with status, tokens and start. */
export function RunTable({
  runs,
  href,
  label = "Run",
  extra = [],
  empty,
}: {
  runs: RunOut[];
  href: (run: RunOut) => string;
  label?: string;
  /** Further columns, with each run's cell and sort value. */
  extra?: { column: Column; cell: (run: RunOut) => ReactNode; sort?: (run: RunOut) => number | string | null }[];
  empty?: ReactNode;
}) {
  const columns: Column[] = [
    { key: "title", label },
    { key: "status", label: "Status" },
    ...extra.map((e) => e.column),
    { key: "tokens", label: "Tokens", align: "right" },
    { key: "started", label: "Started" },
  ];
  const rows: Row[] = runs.map((run) => ({
    id: run.id,
    cells: {
      title: <Link href={href(run)}>{run.title}</Link>,
      status: <StatusBadge status={run.status} />,
      tokens: formatNumber(run.tokens_used),
      started: formatWhen(run.created_at),
      ...Object.fromEntries(extra.map((e) => [e.column.key, e.cell(run)])),
    },
    sort: {
      title: run.title,
      status: run.status,
      tokens: run.tokens_used,
      started: run.created_at,
      ...Object.fromEntries(extra.map((e) => [e.column.key, e.sort?.(run) ?? undefined])),
    },
  }));
  return <DataTable columns={columns} rows={rows} initialSort={{ key: "started", dir: "desc" }} empty={empty} />;
}
