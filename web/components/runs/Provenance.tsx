"use client";

import Link from "next/link";
import { useState, type ReactNode } from "react";

import { LinkButton, Mono, formatNumber, formatWhen, sentenceCase } from "@/components/ui";
import { runLog, type RunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

import { StatusBadge } from "./StatusBadge";

const SEED_NOTES: Record<string, string> = {
  inquiry: "Over the seeds used and every judge rubric",
  tally: "Over the behaviour and its scenario set. Cite rates with it.",
  scenarios: "Over the behaviour's definition and examples",
  ethos: "The seed hash of the run Ethos read",
  witness: "The seed hash of the run the open model read",
};

const ROUTES: Record<string, string> = {
  petri_target: "Petri target: the agent's real prompt, scenario context in a delimited block",
  openai_endpoint: "The adapter's OpenAI-compatible endpoint",
};

/** Everything recorded about a run, each value with the evidence behind it. */
export function Provenance({ run }: { run: RunOut }) {
  const [error, setError] = useState<string | null>(null);
  const config = run.config as { agent?: string; version?: string };

  async function openLog() {
    setError(null);
    const { data } = await runLog({ client: browserClient, path: { run_id: run.id } });
    if (data) window.location.assign(data.url);
    else setError("The log could not be opened. Try again in a moment.");
  }

  const perSample = run.kind === "inquiry" || run.kind === "tally" || run.kind === "ethos";
  const rows: [string, ReactNode][] = [];
  const add = (label: string, value: ReactNode) => rows.push([label, value]);

  add("Status", <StatusBadge status={run.status} />);
  if (config.agent && config.version) {
    add(
      "Prompt",
      <>
        <Link className="ag-link" href={`/agents/${config.agent}/versions/${config.version}`}>
          {config.agent}, {config.version}
        </Link>
        {run.prompt_sha ? <Mono truncate={14}>{run.prompt_sha}</Mono> : null}
      </>,
    );
  }
  add(
    "Models",
    <div className="ag-prov-models">
      {Object.entries(run.model_ids).map(([role, model]) => (
        <span key={role} style={{ display: "contents" }}>
          <span className="ag-muted">{sentenceCase(role)}</span>
          <Mono plain>{String(model)}</Mono>
        </span>
      ))}
    </div>,
  );
  if (run.adapter_mode) add("Mode", sentenceCase(run.adapter_mode));
  if (run.route) add("Route", ROUTES[run.route] ?? run.route);
  add(
    "Config hash",
    <details className="ag-fold">
      <summary>
        <Mono truncate={14}>{run.config_hash}</Mono>
      </summary>
      <div className="ag-fold-body ag-code">{JSON.stringify(run.config, null, 2)}</div>
    </details>,
  );
  if (run.seed_hash) {
    add(
      "Seed hash",
      <>
        <Mono truncate={14}>{run.seed_hash}</Mono>
        <span className="ag-muted">{SEED_NOTES[run.kind] ?? "Over the seeds this run used"}</span>
      </>,
    );
  }
  if (run.taxonomy_version) add("Taxonomy version", <Mono>{run.taxonomy_version}</Mono>);
  const engines = Object.entries(run.engine_versions);
  if (engines.length) {
    add(
      "Engines",
      engines.map(([name, version]) => (
        <Mono key={name} plain>
          {name} {String(version)}
        </Mono>
      )),
    );
  }
  add("Commit", <Mono truncate={9}>{run.git_commit}</Mono>);
  const share = run.token_budget ? Math.min(100, (run.tokens_used / run.token_budget) * 100) : 0;
  add(
    "Tokens",
    <span className="ag-meter">
      <span className="ag-meter-track ag-channel" aria-hidden="true">
        <span style={{ width: `calc(${share}% - 2px)` }} />
      </span>
      <span className="ag-num">
        {formatNumber(run.tokens_used)} of {formatNumber(run.token_budget)}
      </span>
    </span>,
  );
  add("Estimated cost", `US$${run.cost_usd.toFixed(4)}`);
  add("Started", formatWhen(run.started_at, "Not started"));
  add("Finished", formatWhen(run.finished_at, "Still running"));
  if (perSample) {
    add("Inspect logs", <span className="ag-muted">Each sample&apos;s log is on its transcript page</span>);
  } else if (run.kind !== "scenarios") {
    add(
      "Inspect log",
      run.log_uri ? (
        <>
          <LinkButton onClick={openLog}>Download the Inspect log</LinkButton>
          {error ? <span role="alert">{error}</span> : null}
        </>
      ) : (
        <span className="ag-muted">Written when the run finishes</span>
      ),
    );
  }

  return (
    <dl className="ag-prov">
      {rows.map(([label, value]) => (
        <div key={label} style={{ display: "contents" }}>
          <dt>{label}</dt>
          <dd>{value}</dd>
        </div>
      ))}
    </dl>
  );
}
