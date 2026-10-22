import Link from "next/link";

import { StatusBadge } from "@/components/runs/Provenance";
import { formatWhen } from "@/components/ui";
import type { TallyRunSummary } from "@/lib/api";

import { meanText, percent, spreadText, tallyText } from "./format";
import styles from "./tally.module.css";

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

/** The numbers behind the rate chart, each linked to its run. */
export function RateTable({ runs }: { runs: TallyRunSummary[] }) {
  return (
    <table className={styles.numbers}>
      <thead>
        <tr>
          <th scope="col">Prompt version</th>
          <th scope="col">Rate</th>
          <th scope="col">Scored 7 or more</th>
          <th scope="col">Repetitions</th>
          <th scope="col">Mean presence</th>
          <th scope="col">Status</th>
          <th scope="col">Started</th>
        </tr>
      </thead>
      <tbody>
        {runs.map((run) => {
          const { overall } = run.elicitation;
          const href = `/tally/runs/${run.run.id}`;
          return (
            <tr key={run.run.id}>
              <td>
                <Link href={`/agents/${run.agent}/versions/${run.version}`}>
                  {run.agent} {run.version}
                </Link>
              </td>
              <td>
                <Link href={href}>{percent(overall.rate)}</Link>
              </td>
              <td>
                <Link href={`${href}#rollouts`}>{tallyText(overall)}</Link>
                {overall.unscored ? `, ${overall.unscored} unscored` : ""}
              </td>
              <td>
                <Link href={`${href}#repetitions`}>{spreadText(run.elicitation)}</Link>
              </td>
              <td>{meanText(overall)}</td>
              <td>
                <StatusBadge status={run.run.status} />
              </td>
              <td>{formatWhen(run.run.created_at)}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}
