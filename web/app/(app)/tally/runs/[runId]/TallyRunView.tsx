"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { ScoreCell } from "@/components/data/ScoreCell";
import { Provenance } from "@/components/runs/Provenance";
import { RunProgress } from "@/components/runs/RunProgress";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { meanText, percent, spreadText, tallyText } from "@/components/tally/format";
import { Badge, Card, LinkButton, Mono, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readTallyRun, type TallyRunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

function label(value: string): string {
  return sentenceCase(value.replaceAll("_", " "));
}

export function TallyRunView({ run }: { run: TallyRunOut }) {
  const router = useRouter();
  // The counts below link here with a filter, so each number opens the rollouts behind it.
  const params = useSearchParams();
  const repetition = params.get("repetition");
  const only = params.get("scenario");
  const rollouts = run.rollouts.filter(
    (r) => (!repetition || String(r.epoch) === repetition) && (!only || r.scenario === only),
  );
  const initial: Live = { status: run.run.status, tokens_used: run.run.tokens_used, counts: run.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/tally/runs/${run.run.id}/events`,
    poll: async () => {
      const { data } = await readTallyRun({ client: browserClient, path: { run_id: run.run.id } });
      return data ? { status: data.run.status, tokens_used: data.run.tokens_used, counts: data.counts } : null;
    },
    done: (value) => !OPEN.has(value.status),
    initial,
  });
  const seen = useRef(JSON.stringify(initial));
  useEffect(() => {
    const next = JSON.stringify(live);
    if (live && next !== seen.current) {
      seen.current = next;
      router.refresh();
    }
  }, [live, router]);

  const status = live?.status ?? run.run.status;
  const counts = live?.counts ?? run.counts;
  const { elicitation } = run;
  const threshold = elicitation.threshold;

  const epochs: Row[] = elicitation.by_epoch.map((epoch) => ({
    id: String(epoch.epoch),
    cells: {
      epoch: epoch.epoch,
      rate: percent(epoch.rate),
      scored: <Link href={`?repetition=${epoch.epoch}#rollouts`}>{tallyText(epoch)}</Link>,
      mean: meanText(epoch),
    },
    sort: { epoch: epoch.epoch, rate: epoch.rate, scored: epoch.elicited, mean: epoch.mean_score },
  }));
  const scenarios: Row[] = run.by_scenario.map((scenario) => ({
    id: scenario.scenario,
    cells: {
      scenario: (
        <Link href={`/tally/scenario-sets/${run.scenario_set}#scenario-${scenario.scenario}`}>{label(scenario.scenario)}</Link>
      ),
      variation: scenario.variation ? label(scenario.variation) : "Base",
      scored: <Link href={`?scenario=${scenario.scenario}#rollouts`}>{tallyText(scenario)}</Link>,
      mean: meanText(scenario),
    },
    sort: { scenario: scenario.scenario, variation: scenario.variation ?? "", scored: scenario.elicited, mean: scenario.mean_score },
  }));
  const rows: Row[] = rollouts.map((rollout) => ({
    id: rollout.transcript_id,
    cells: {
      presence:
        rollout.score === null || rollout.score === undefined ? (
          <Link href={`/tally/transcripts/${rollout.transcript_id}`}>
            <Badge>Not scored</Badge>
          </Link>
        ) : (
          <ScoreCell
            value={rollout.score}
            threshold={threshold}
            label="Presence"
            href={`/tally/transcripts/${rollout.transcript_id}`}
          />
        ),
      scenario: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          {label(rollout.scenario)}
          {rollout.content_notes.map((note) => (
            <Badge key={note} tone="warn">
              Content note: {label(note).toLowerCase()}
            </Badge>
          ))}
        </span>
      ),
      epoch: rollout.epoch,
      summary: <span className="ag-muted">{rollout.summary}</span>,
    },
    sort: { presence: rollout.score ?? -1, scenario: rollout.scenario, epoch: rollout.epoch },
  }));

  return (
    <>
      <PageHeader
        title={run.run.title}
        actions={OPEN.has(status) ? null : <LinkButton href={`/ethos?source=${run.run.id}`}>Read these conversations with Ethos</LinkButton>}
      >
        <p>
          <Link href={`/agents/${run.agent}/versions/${run.version}`}>
            {run.agent} {run.version}
          </Link>{" "}
          on <Link href={`/tally/behaviours/${run.behaviour}?set=${run.scenario_set}`}>{label(run.behaviour)}</Link>, using{" "}
          <Link href={`/tally/scenario-sets/${run.scenario_set}`}>its scenario set</Link>. <StatusBadge status={status} />
        </p>
      </PageHeader>
      <Card title="Progress">
        <RunProgress counts={counts} unit="rollouts" />
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
      </Card>
      <Card title="Elicitation rate">
        <dl className="ag-stats">
          <div className="ag-stat">
            <dt>Rate</dt>
            <dd>
              <a href="#rollouts">{percent(elicitation.overall.rate)}</a>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Scored {threshold} or more</dt>
            <dd>
              <a href="#rollouts">{tallyText(elicitation.overall)}</a>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Across repetitions</dt>
            <dd>
              <a href="#repetitions">{spreadText(elicitation)}</a>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Mean presence</dt>
            <dd>
              <a href="#rollouts">{meanText(elicitation.overall)}</a>
            </dd>
          </div>
        </dl>
        <p className="ag-quiet">
          Cite this rate with its seed hash, <Mono truncate={16}>{run.run.seed_hash ?? ""}</Mono>.
          {elicitation.overall.unscored
            ? ` ${elicitation.overall.unscored} rollouts the judge did not score are left out.`
            : ""}
        </p>
        <h3 id="repetitions">Each repetition</h3>
        <DataTable
          density="dense"
          columns={[
            { key: "epoch", label: "Repetition", align: "right" },
            { key: "rate", label: "Rate", align: "right" },
            { key: "scored", label: `Scored ${threshold} or more`, align: "right" },
            { key: "mean", label: "Mean presence", align: "right" },
          ]}
          rows={epochs}
        />
      </Card>
      <Card title="By scenario">
        <DataTable
          columns={[
            { key: "scenario", label: "Scenario" },
            { key: "variation", label: "Variation" },
            { key: "scored", label: `Scored ${threshold} or more`, align: "right" },
            { key: "mean", label: "Mean presence", align: "right" },
          ]}
          rows={scenarios}
          maxHeight={480}
        />
      </Card>
      <Card
        title="Rollouts"
        id="rollouts"
        actions={repetition || only ? <LinkButton href="?#rollouts">Show every rollout</LinkButton> : null}
      >
        <p className="ag-quiet">
          {repetition || only
            ? `Showing ${only ? label(only) : "every scenario"}${repetition ? `, repetition ${repetition}` : ""}: `
            : ""}
          {rows.length} {rows.length === 1 ? "rollout" : "rollouts"}, the highest presence first.
        </p>
        <DataTable
          columns={[
            { key: "presence", label: "Presence" },
            { key: "scenario", label: "Scenario" },
            { key: "epoch", label: "Repetition", align: "right" },
            { key: "summary", label: "Judge’s summary", sortable: false },
          ]}
          rows={rows}
          initialSort={{ key: "presence", dir: "desc" }}
          empty="No rollouts match."
        />
      </Card>
      <Card title="Run">
        <Provenance run={run.run} />
      </Card>
    </>
  );
}
