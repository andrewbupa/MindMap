import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { ScoreCell } from "@/components/data/ScoreCell";
import { Fold } from "@/components/runs/Messages";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { GenerationPanel } from "@/components/tally/GenerationPanel";
import { RateChart } from "@/components/tally/RateChart";
import { RateTable, latestByVersion } from "@/components/tally/RateTable";
import { Badge, ButtonLink, Card, EmptyState, Mono, PageHeader, formatNumber, formatWhen, sentenceCase } from "@/components/ui";
import { readBehaviour } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Behaviour" };

const words = (value: string) => sentenceCase(value.replaceAll("_", " "));

export default async function BehaviourPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ set?: string }>;
}) {
  const [{ key }, { set }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const [user, { data: behaviour }] = await Promise.all([
    getMe(),
    readBehaviour({ client, path: { key }, query: { scenario_set: set }, throwOnError: true }),
  ]);
  const author = user !== null && hasRole(user, "author");
  const selected = behaviour.scenario_sets.find((item) => item.id === behaviour.selected_set);
  const latest = latestByVersion(behaviour.runs);
  const earlier = behaviour.runs.filter((run) => !latest.includes(run));
  const start = author && selected ? `/tally/new?behaviour=${behaviour.key}&set=${selected.id}` : null;

  const rollouts: Row[] = behaviour.top_rollouts.map((rollout) => ({
    id: rollout.transcript_id,
    cells: {
      presence: (
        <ScoreCell value={rollout.score ?? 0} label="Presence" href={`/tally/transcripts/${rollout.transcript_id}`} />
      ),
      scenario: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          {words(rollout.scenario)}
          {rollout.variation ? <Badge>{words(rollout.variation)}</Badge> : null}
          {rollout.content_notes.map((note) => (
            <Badge key={note} tone="warn">
              Content note: {words(note).toLowerCase()}
            </Badge>
          ))}
        </span>
      ),
      version: <Mono plain>{rollout.version}</Mono>,
      epoch: rollout.epoch,
      summary: <span className="ag-muted">{rollout.summary}</span>,
    },
    sort: { presence: rollout.score, scenario: rollout.scenario, version: rollout.version, epoch: rollout.epoch },
  }));

  return (
    <>
      <PageHeader
        title={behaviour.title}
        intro={behaviour.definition.split("\n\n")[0]}
        actions={start ? <ButtonLink href={start}>Start a suite on this scenario set</ButtonLink> : null}
      />

      <Card title="Elicitation rate by prompt version">
        {selected ? (
          <p className="ag-quiet">
            On scenario set{" "}
            <Link href={`/tally/scenario-sets/${selected.id}`}>
              <Mono>{selected.content_hash.slice(0, 12)}</Mono>
            </Link>{" "}
            ({selected.scenario_count} scenarios, generated {formatWhen(selected.created_at)}). The rate is the share of
            rollouts scoring 7 or more of 10 for presence; the whiskers span the repetitions. Rates are comparable only
            within one scenario set.
          </p>
        ) : null}
        {latest.length ? (
          <div style={{ display: "grid", gap: "var(--space-4)" }}>
            <RateChart
              points={latest.map((run) => ({
                label: run.version,
                href: `/tally/runs/${run.run.id}`,
                elicitation: run.elicitation,
              }))}
            />
            <RateTable runs={latest} caption="The numbers behind the chart" />
          </div>
        ) : (
          <EmptyState title="No finished suites on this scenario set" action={start ? <ButtonLink href={start}>Start a suite</ButtonLink> : null}>
            A suite runs every scenario against each prompt version you choose.
          </EmptyState>
        )}
        {earlier.length ? (
          <div style={{ marginTop: "var(--space-4)" }}>
            <Fold summary={`Earlier and unfinished runs (${earlier.length})`}>
              <RateTable runs={earlier} />
            </Fold>
          </div>
        ) : null}
      </Card>

      <Card title="Highest presence scores">
        {rollouts.length === 0 ? (
          <p>No scored rollouts yet.</p>
        ) : (
          <DataTable
            columns={[
              { key: "presence", label: "Presence" },
              { key: "scenario", label: "Scenario" },
              { key: "version", label: "Prompt version" },
              { key: "epoch", label: "Repetition", align: "right" },
              { key: "summary", label: "Judge’s summary", sortable: false },
            ]}
            rows={rollouts}
            initialSort={{ key: "presence", dir: "desc" }}
          />
        )}
      </Card>

      <Card title="Scenarios">
        {behaviour.scenario_set ? (
          <p>
            The current scenario set has{" "}
            <Link href={`/tally/scenario-sets/${behaviour.scenario_set.id}`}>
              {behaviour.scenario_set.scenario_count} scenarios
            </Link>
            : base scenarios Bloom wrote from the definition, and a variation of each for{" "}
            {behaviour.variations.map((v) => v.replaceAll("_", " ")).join(" and ")}. The judge scores presence on{" "}
            <Mono>{behaviour.scenario_set.presence_dimension}</Mono>.
          </p>
        ) : (
          <p>
            This version of the behaviour has no scenarios yet. Generation runs Bloom&apos;s understanding and ideation
            once; every suite then reuses the result.
          </p>
        )}
        <GenerationPanel
          behaviour={behaviour.key}
          generating={behaviour.generating}
          canGenerate={author}
          hasCurrent={behaviour.scenario_set !== null}
        />
        {behaviour.scenario_sets.length > 1 ? (
          <div style={{ marginTop: "var(--space-5)" }}>
            <h3>Every scenario set</h3>
            <DataTable
              columns={[
                { key: "set", label: "Set" },
                { key: "count", label: "Scenarios", align: "right" },
                { key: "version", label: "Behaviour version" },
                { key: "generated", label: "Generated" },
              ]}
              rows={behaviour.scenario_sets.map((item) => ({
                id: item.id,
                cells: {
                  set: (
                    <span className="ag-row" style={{ gap: "var(--space-2)" }}>
                      <Link href={`/tally/behaviours/${behaviour.key}?set=${item.id}`}>
                        <Mono>{item.content_hash.slice(0, 12)}</Mono>
                      </Link>
                      {item.id === behaviour.selected_set ? <Badge>Shown</Badge> : null}
                    </span>
                  ),
                  count: <Link href={`/tally/scenario-sets/${item.id}`}>{item.scenario_count}</Link>,
                  version: item.current ? "Current" : "Earlier",
                  generated: formatWhen(item.created_at),
                },
                sort: { count: item.scenario_count, generated: item.created_at },
              }))}
            />
          </div>
        ) : null}
        {behaviour.generations.length ? (
          <div style={{ marginTop: "var(--space-4)" }}>
            <Fold summary={`Generation runs (${behaviour.generations.length})`}>
              <DataTable
                density="dense"
                columns={[
                  { key: "when", label: "Started" },
                  { key: "status", label: "Status" },
                  { key: "tokens", label: "Tokens", align: "right" },
                  { key: "error", label: "Error", sortable: false },
                ]}
                rows={behaviour.generations.map((run) => ({
                  id: run.id,
                  cells: {
                    when: formatWhen(run.created_at),
                    status: <StatusBadge status={run.status} />,
                    tokens: formatNumber(run.tokens_used),
                    error: <span className="ag-muted">{run.error}</span>,
                  },
                }))}
              />
            </Fold>
          </div>
        ) : null}
      </Card>

      <Card title="Behaviour version">
        <dl className="ag-prov">
          <dt>Seed hash</dt>
          <dd>
            <Mono truncate={16}>{behaviour.seed_hash}</Mono>
            <span className="ag-muted">
              Over seeds/bloom/{behaviour.key}. Cite every rate with its run&apos;s seed hash.
            </span>
          </dd>
          <dt>Agents</dt>
          <dd>{behaviour.agents.join(", ") || "Any"}</dd>
          <dt>Variations</dt>
          <dd>{behaviour.variations.map(words).join(", ")}</dd>
          <dt>Ethos scenario type</dt>
          <dd>{behaviour.scenario_type ? words(behaviour.scenario_type) : "None"}</dd>
        </dl>
        <div style={{ marginTop: "var(--space-4)" }}>
          <Fold summary="The full definition">{behaviour.definition}</Fold>
        </div>
      </Card>
    </>
  );
}
