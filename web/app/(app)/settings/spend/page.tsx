import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { KIND_NAMES } from "@/components/runs/href";
import { Card, Mono, Notice, PageHeader, formatMonth, formatNumber, formatUsd } from "@/components/ui";
import { spend } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Spend" };

export default async function SpendPage() {
  const { data } = await spend({ client: await serverClient(), query: { months: 12 }, throwOnError: true });
  // Months before the first run say nothing; keep the current month even when empty.
  const last = data.months.findLastIndex((month) => month.runs > 0);
  const shown = data.months.slice(0, Math.max(1, last + 1));
  const rows: Row[] = shown.map((month) => {
    const record = `/record?month=${month.month}`;
    return {
      id: month.month,
      cells: {
        month: <Link href={record}>{formatMonth(month.month)}</Link>,
        runs: month.runs ? <Link href={record}>{month.runs}</Link> : 0,
        tokens: formatNumber(month.tokens),
        cost: <span className="ag-num">{formatUsd(month.cost_usd)}</span>,
        kinds: month.runs ? (
          <span className="ag-row" style={{ gap: "var(--space-2)" }}>
            {Object.entries(month.by_kind).map(([kind, part]) => (
              <Link key={kind} href={`${record}&kind=${kind}`} className="ag-badge">
                {KIND_NAMES[kind] ?? kind}: {formatUsd(part.cost_usd)}
              </Link>
            ))}
          </span>
        ) : (
          <span className="ag-muted">No runs</span>
        ),
      },
      sort: { month: month.month, runs: month.runs, tokens: month.tokens, cost: month.cost_usd },
    };
  });
  return (
    <>
      <PageHeader
        title="Spend"
        intro={`Estimated from each run's tokens and the prices in config/models.yaml, by the month the run started, in ${data.time_zone.replace("_", " ")} time. Providers' invoices are the final word.`}
      />
      {data.unpriced_models.length ? (
        <Notice title="Some models have no price">
          Their tokens count as nothing here, so these figures are too low until a price is set in{" "}
          <Mono plain>config/models.yaml</Mono>:{" "}
          {data.unpriced_models.map((model, index) => (
            <span key={model}>
              {index ? ", " : ""}
              <Mono plain>{model}</Mono>
            </span>
          ))}
          .
        </Notice>
      ) : null}
      <Card title="By month">
        <DataTable
          columns={[
            { key: "month", label: "Month", nowrap: true },
            { key: "runs", label: "Runs", align: "right" },
            { key: "tokens", label: "Tokens", align: "right" },
            { key: "cost", label: "Estimated cost", align: "right" },
            { key: "kinds", label: "By kind", sortable: false },
          ]}
          rows={rows}
          initialSort={{ key: "month", dir: "desc" }}
        />
      </Card>
    </>
  );
}
