import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { Fold } from "@/components/runs/Messages";
import { Provenance } from "@/components/runs/Provenance";
import { Badge, Card, Mono, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { readScenarioSet } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Scenario set" };

const words = (value: string) => sentenceCase(value.replaceAll("_", " "));

export default async function ScenarioSetPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = await params;
  const { data: set } = await readScenarioSet({
    client: await serverClient(),
    path: { scenario_set_id: setId },
    throwOnError: true,
  });
  const rows: Row[] = set.scenarios.map((scenario) => ({
    id: scenario.id,
    cells: {
      scenario: (
        <div id={`scenario-${scenario.id}`}>
          <Fold summary={words(scenario.id)}>{scenario.seed}</Fold>
        </div>
      ),
      variation: scenario.variation ? <Badge>{words(scenario.variation)}</Badge> : <span className="ag-muted">Base scenario</span>,
    },
    sort: { scenario: scenario.id, variation: scenario.variation ?? "" },
  }));
  return (
    <>
      <PageHeader title={`Scenarios: ${words(set.behaviour)}`}>
        <p>
          Bloom wrote these from{" "}
          <Link href={`/tally/behaviours/${set.behaviour}?set=${set.summary.id}`}>the behaviour&apos;s definition</Link> on{" "}
          {formatWhen(set.summary.created_at)}
          {set.summary.current ? "" : ", from an earlier version of it"}. They never change; a new set is a new
          generation.
        </p>
      </PageHeader>
      <Card title={`Scenarios (${set.scenarios.length})`}>
        <DataTable
          columns={[
            { key: "scenario", label: "Scenario" },
            { key: "variation", label: "Variation" },
          ]}
          rows={rows}
        />
      </Card>
      <Card title="Judge dimensions">
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {set.dimensions.map((dimension) => (
            <Fold
              key={dimension.name}
              open={dimension.presence}
              summary={
                <span className="ag-row" style={{ gap: "var(--space-2)" }}>
                  <Mono plain>{dimension.name}</Mono>
                  {dimension.presence ? <Badge>Presence</Badge> : null}
                </span>
              }
            >
              {dimension.description}
              {dimension.rubric ? `\n\n${dimension.rubric}` : ""}
            </Fold>
          ))}
        </div>
      </Card>
      <Card title="Bloom’s understanding">
        {set.understanding ? <p style={{ whiteSpace: "pre-wrap" }}>{set.understanding}</p> : <p>None recorded.</p>}
        {set.scientific_motivation ? <Fold summary="Why it is worth measuring">{set.scientific_motivation}</Fold> : null}
      </Card>
      <Card title="Generation">
        <dl className="ag-prov" style={{ marginBottom: "var(--space-4)" }}>
          <dt>Content hash</dt>
          <dd>
            <Mono truncate={16}>{set.summary.content_hash}</Mono>
          </dd>
          <dt>Behaviour seed hash</dt>
          <dd>
            <Mono truncate={16}>{set.summary.behaviour_seed_hash}</Mono>
          </dd>
        </dl>
        <Provenance run={set.generation} />
      </Card>
    </>
  );
}
