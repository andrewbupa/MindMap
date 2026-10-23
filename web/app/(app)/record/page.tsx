import Link from "next/link";

import { RunTable } from "@/components/runs/RunTable";
import { KIND_NAMES, runHref } from "@/components/runs/href";
import { Card, EmptyState, LinkButton, PageHeader, formatMonth, formatUsd } from "@/components/ui";
import { listReportRuns, type RunOut } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Record" };

const FINISHED = new Set(["succeeded", "failed", "cancelled", "stopped_at_budget"]);

function Exports({ run }: { run: RunOut }) {
  const base = `/api/record/runs/${run.id}`;
  const links: { href: string; label: string }[] = [];
  if (FINISHED.has(run.status)) {
    links.push({ href: `${base}/report.pdf`, label: "Report (PDF)" });
    if (run.kind === "inquiry" || run.kind === "tally") links.push({ href: `${base}/scores.csv`, label: "Scores (CSV)" });
    if (run.kind === "ethos") links.push({ href: `${base}/findings.csv`, label: "Findings (CSV)" });
  }
  links.push({ href: `${base}/provenance`, label: "Provenance (JSON)" });
  return (
    <span className="ag-row" style={{ gap: "var(--space-3)" }}>
      {links.map((link) => (
        <a key={link.href} href={link.href} className="ag-link">
          {link.label}
          <span className="ag-sr">: {run.title}</span>
        </a>
      ))}
    </span>
  );
}

export default async function RecordPage({
  searchParams,
}: {
  searchParams: Promise<{ kind?: string; month?: string }>;
}) {
  const { kind, month: asked } = await searchParams;
  const month = asked && /^\d{4}-(0[1-9]|1[0-2])$/.test(asked) ? asked : undefined;
  const { data: runs } = await listReportRuns({
    client: await serverClient(),
    query: month ? { month, limit: 1000 } : {},
    throwOnError: true,
  });
  const within = (value: string) => {
    const query = new URLSearchParams({ ...(month ? { month } : {}), ...(value ? { kind: value } : {}) });
    return query.size ? `/record?${query}` : "/record";
  };
  const kinds = [...new Set(runs.map((run) => run.kind))].sort();
  const shown = kind ? runs.filter((run) => run.kind === kind) : runs;
  const tabs = [{ value: "", label: "Every kind" }, ...kinds.map((k) => ({ value: k, label: KIND_NAMES[k] ?? k }))];
  return (
    <>
      <PageHeader
        title="Record"
        intro="Export a run with its full provenance: commit, config hash, prompt, seed hash, taxonomy version and the exact models. The PDF opens with all of it; every CSV row carries it. Every export is recorded in the audit log."
      />
      <nav aria-label="Kinds of run" style={{ marginBottom: "var(--space-5)" }}>
        <ul className="ag-tabs ag-tab-links">
          {tabs.map((tab) => (
            <li key={tab.value}>
              <Link
                href={within(tab.value)}
                className="ag-tab"
                aria-current={(kind ?? "") === tab.value ? "page" : undefined}
              >
                {tab.label}
                <span className="ag-count">
                  {tab.value ? runs.filter((run) => run.kind === tab.value).length : runs.length}
                </span>
              </Link>
            </li>
          ))}
        </ul>
      </nav>
      {month ? (
        <p className="ag-quiet">
          Runs started in {formatMonth(month)}.{" "}
          <LinkButton href={kind ? `/record?kind=${kind}` : "/record"}>Show every month</LinkButton>
        </p>
      ) : null}
      <Card label="Runs">
        <RunTable
          runs={shown}
          href={(run) => runHref(run) ?? "/record"}
          extra={[
            {
              column: { key: "kind", label: "Kind" },
              cell: (run) => KIND_NAMES[run.kind] ?? run.kind,
              sort: (run) => run.kind,
            },
            {
              column: { key: "cost", label: "Estimated cost", align: "right", nowrap: true },
              cell: (run) => <span className="ag-num">{formatUsd(run.cost_usd)}</span>,
              sort: (run) => run.cost_usd,
            },
            {
              column: { key: "exports", label: "Exports", sortable: false },
              cell: (run) => <Exports run={run} />,
            },
          ]}
          empty={<EmptyState title="No runs yet">Runs appear here as soon as they are launched.</EmptyState>}
        />
      </Card>
    </>
  );
}
