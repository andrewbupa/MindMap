import Link from "next/link";

import { StatusBadge } from "@/components/runs/StatusBadge";
import { DataTable, type Column, type Row } from "@/components/data/DataTable";
import { Badge, Mono, formatWhen } from "@/components/ui";
import type { TallyRunSummary } from "@/lib/api";

import { meanText, percent, spreadText, tallyText } from "./format";

const FINISHED = new Set(["succeeded", "stopped_at_budget"]);

function versionKey(version: string): number[] {
  return (version.match(/\d+/g) ?? []).map(Number);
}

export function compareVersions(a: string, b: string): number {
  const left = versionKey(a);
  const right = versionKey(b);
  for (let i = 0; i < Math.max(left.length, right.length); i += 1) {
    const diff = (left[i] ?? 0) - (right[i] ?? 0);
    if (diff) return diff;
  }
  return a.localeCompare(b);
}

/** The newest finished run for each prompt version, in version order. */
export function latestByVersion(runs: TallyRunSummary[]): TallyRunSummary[] {
  const latest = new Map<string, TallyRunSummary>();
  for (const run of runs) {
    if (!FINISHED.has(run.run.status)) continue;
    const key = `${run.agent} ${run.version}`;
    const seen = latest.get(key);
    if (!seen || seen.run.created_at < run.run.created_at) latest.set(key, run);
  }
  return [...latest.values()].sort(
    (a, b) => a.agent.localeCompare(b.agent) || compareVersions(a.version, b.version),
  );
}

/** The numbers behind the rate chart, each linked to its run, with the change from the
 * version before: a higher rate of the behaviour is worse. */
export function RateTable({ runs, caption }: { runs: TallyRunSummary[]; caption?: string }) {
  const columns: Column[] = [
    { key: "version", label: "Prompt version" },
    { key: "rate", label: "Rate", align: "right" },
    { key: "scored", label: "Scored 7 or more", align: "right" },
    { key: "spread", label: "Spread", align: "right" },
    { key: "mean", label: "Mean presence", align: "right" },
    { key: "change", label: "Change", nowrap: true },
    { key: "status", label: "Status" },
    { key: "started", label: "Started", nowrap: true },
  ];
  const rows: Row[] = runs.map((run, index) => {
    const { overall } = run.elicitation;
    const href = `/tally/runs/${run.run.id}`;
    const before = runs[index - 1];
    const rate = overall.rate === null || overall.rate === undefined ? null : Math.round(overall.rate * 100);
    const previous =
      before && before.agent === run.agent && before.elicitation.overall.rate !== null && before.elicitation.overall.rate !== undefined
        ? Math.round(before.elicitation.overall.rate * 100)
        : null;
    const change =
      rate === null || previous === null ? (
        <span className="ag-muted">{previous === null && before?.agent !== run.agent ? "First version" : "Not scored"}</span>
      ) : rate > previous ? (
        <Badge tone="danger">Worse by {rate - previous} points</Badge>
      ) : rate < previous ? (
        <Badge tone="ok">Better by {previous - rate} points</Badge>
      ) : (
        <Badge>No change</Badge>
      );
    return {
      id: run.run.id,
      cells: {
        version: (
          <Link href={`/agents/${run.agent}/versions/${run.version}`}>
            <Mono plain>
              {run.agent} {run.version}
            </Mono>
          </Link>
        ),
        rate: <Link href={href}>{percent(overall.rate)}</Link>,
        scored: (
          <>
            <Link href={`${href}#rollouts`}>{tallyText(overall)}</Link>
            {overall.unscored ? `, ${overall.unscored} unscored` : ""}
          </>
        ),
        spread: <Link href={`${href}#repetitions`}>{spreadText(run.elicitation)}</Link>,
        mean: meanText(overall),
        change,
        status: <StatusBadge status={run.run.status} />,
        started: formatWhen(run.run.created_at),
      },
    };
  });
  return <DataTable columns={columns} rows={rows} caption={caption} />;
}
