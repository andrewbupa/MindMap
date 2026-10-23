import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { RunTable } from "@/components/runs/RunTable";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { percent } from "@/components/tally/format";
import { latestByVersion } from "@/components/tally/RateTable";
import { Badge, Card, EmptyState, PageHeader, sentenceCase } from "@/components/ui";
import { listBehaviours, listTallyRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Tally" };

export default async function TallyPage() {
  const client = await serverClient();
  const [{ data: behaviours }, { data: runs }] = await Promise.all([
    listBehaviours({ client, throwOnError: true }),
    listTallyRuns({ client, throwOnError: true }),
  ]);
  const rates = new Map(runs.map((run) => [run.run.id, run.elicitation.overall.rate]));

  const rows: Row[] = behaviours.map((behaviour) => {
    const latest = latestByVersion(runs.filter((run) => run.behaviour === behaviour.key));
    return {
      id: behaviour.key,
      cells: {
        behaviour: (
          <span className="ag-row" style={{ gap: "var(--space-2)" }}>
            <Link href={`/tally/behaviours/${behaviour.key}`}>{behaviour.title}</Link>
            {behaviour.content_notes.map((note) => (
              <Badge key={note} tone="warn">
                Content note: {sentenceCase(note.replaceAll("_", " ")).toLowerCase()}
              </Badge>
            ))}
          </span>
        ),
        agents: behaviour.agents.join(", ") || "Any",
        scenarios: behaviour.generating ? (
          <StatusBadge status={behaviour.generating.status} />
        ) : behaviour.scenario_set ? (
          <Link href={`/tally/scenario-sets/${behaviour.scenario_set.id}`}>
            {behaviour.scenario_set.scenario_count} scenarios
          </Link>
        ) : (
          <span className="ag-muted">Not generated yet</span>
        ),
        rates:
          latest.length === 0 ? (
            <span className="ag-muted">No suites yet</span>
          ) : (
            <span className="ag-row" style={{ gap: "var(--space-3)" }}>
              {latest.map((run) => (
                <span key={run.run.id} className="ag-num">
                  {run.version}{" "}
                  <Link href={`/tally/runs/${run.run.id}`}>{percent(run.elicitation.overall.rate)}</Link>
                </span>
              ))}
            </span>
          ),
      },
      sort: { behaviour: behaviour.title, scenarios: behaviour.scenario_set?.scenario_count ?? null },
    };
  });

  return (
    <>
      <PageHeader
        title="Tally"
        intro="Bloom turns one behaviour into a rate: the share of conversations a judge scores 7 or more out of 10 for it. Each prompt version faces the same generated scenarios, three times over, so rates can be compared."
      />
      <Card title="Behaviours">
        <DataTable
          columns={[
            { key: "behaviour", label: "Behaviour" },
            { key: "agents", label: "Agents", sortable: false },
            { key: "scenarios", label: "Scenarios" },
            { key: "rates", label: "Latest rates by prompt version", sortable: false },
          ]}
          rows={rows}
          empty="No behaviours yet. Add one under seeds/bloom."
        />
      </Card>
      <Card title="Recent suites">
        <RunTable
          runs={runs.slice(0, 20).map((run) => run.run)}
          href={(run) => `/tally/runs/${run.id}`}
          extra={[
            {
              column: { key: "rate", label: "Elicitation rate", align: "right" },
              cell: (run) => <Link href={`/tally/runs/${run.id}#rollouts`}>{percent(rates.get(run.id))}</Link>,
              sort: (run) => rates.get(run.id) ?? null,
            },
          ]}
          empty={
            <EmptyState title="No suites yet">
              Generate a behaviour&apos;s scenarios, then start a suite from its page.
            </EmptyState>
          }
        />
      </Card>
    </>
  );
}
