"use client";

import Link from "next/link";
import { useState } from "react";

import { Badge, LinkButton, Mono, formatWhen, sentenceCase, type Tone } from "@/components/ui";
import { runLog, type RunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

import styles from "./runs.module.css";

const STATUS_TONES: Record<string, Tone> = {
  running: "warn",
  succeeded: "ok",
  failed: "danger",
  stopped_at_budget: "warn",
};

const SEED_NOTES: Record<string, string> = {
  explore: "Over the seeds used and every judge rubric",
  measure: "Over the behaviour and its scenario set. Cite rates with it.",
  scenarios: "Over the behaviour's definition and examples",
  lens: "The seed hash of the run Lens read",
  companion: "The seed hash of the run the open model read",
};

const ROUTES: Record<string, string> = {
  petri_target: "Petri target: the agent's real prompt, scenario context in a delimited block",
  openai_endpoint: "The adapter's OpenAI-compatible endpoint",
};

export function StatusBadge({ status }: { status: string }) {
  return <Badge tone={STATUS_TONES[status] ?? "neutral"}>{sentenceCase(status)}</Badge>;
}

/** Everything recorded about a run, with each value linked to the evidence behind it. */
export function Provenance({ run }: { run: RunOut }) {
  const [error, setError] = useState<string | null>(null);
  const config = run.config as { agent?: string; version?: string };

  async function openLog() {
    setError(null);
    const { data } = await runLog({ client: browserClient, path: { run_id: run.id } });
    if (data) window.location.assign(data.url);
    else setError("The log could not be opened.");
  }

  const perSample = run.kind === "explore" || run.kind === "measure" || run.kind === "lens";
  const seedNote = SEED_NOTES[run.kind] ?? "Over the seeds this run used";
  const log = run.log_uri ? (
    <LinkButton onClick={openLog} title="Download the Inspect .eval log">
      Inspect log
    </LinkButton>
  ) : (
    "Written when the run finishes"
  );

  return (
    <table className={styles.provenance}>
      <tbody>
        <tr>
          <th scope="row">Status</th>
          <td>
            <StatusBadge status={run.status} />
          </td>
        </tr>
        {config.agent && config.version ? (
          <tr>
            <th scope="row">Prompt</th>
            <td>
              <Link href={`/agents/${config.agent}/versions/${config.version}`}>
                {config.agent} {config.version}
              </Link>
              <br />
              <Mono>{run.prompt_sha?.slice(0, 16)}</Mono>
            </td>
          </tr>
        ) : null}
        {Object.entries(run.model_ids).map(([role, model]) => (
          <tr key={role}>
            <th scope="row">{sentenceCase(role)} model</th>
            <td>
              <Mono>{String(model)}</Mono>
            </td>
          </tr>
        ))}
        <tr>
          <th scope="row">Mode</th>
          <td>{run.adapter_mode ? sentenceCase(run.adapter_mode) : "Not applicable"}</td>
        </tr>
        {run.route ? (
          <tr>
            <th scope="row">Route</th>
            <td>{ROUTES[run.route] ?? run.route}</td>
          </tr>
        ) : null}
        <tr>
          <th scope="row">Config hash</th>
          <td>
            <details>
              <summary>
                <Mono>{run.config_hash.slice(0, 16)}</Mono>
              </summary>
              <pre className={styles.quiet}>{JSON.stringify(run.config, null, 2)}</pre>
            </details>
          </td>
        </tr>
        {run.seed_hash ? (
          <tr>
            <th scope="row">Seed hash</th>
            <td>
              <Mono>{run.seed_hash.slice(0, 16)}</Mono>
              <br />
              <span className={styles.quiet}>{seedNote}</span>
            </td>
          </tr>
        ) : null}
        {Object.keys(run.engine_versions).length ? (
          <tr>
            <th scope="row">Engines</th>
            <td>
              {Object.entries(run.engine_versions).map(([name, version]) => (
                <div key={name}>
                  <Mono>
                    {name} {String(version)}
                  </Mono>
                </div>
              ))}
            </td>
          </tr>
        ) : null}
        <tr>
          <th scope="row">Commit</th>
          <td>
            <Mono>{run.git_commit.slice(0, 12)}</Mono>
          </td>
        </tr>
        <tr>
          <th scope="row">Tokens</th>
          <td>
            {run.tokens_used.toLocaleString("en-AU")} of {run.token_budget.toLocaleString("en-AU")}
            <br />
            <span className={styles.quiet}>
              Counted per model call
              {perSample
                ? "; each sample's log is on its transcript page."
                : run.log_uri
                  ? <>; each call is in the {log}</>
                  : "."}
            </span>
          </td>
        </tr>
        <tr>
          <th scope="row">Estimated cost</th>
          <td>US${run.cost_usd.toFixed(4)}</td>
        </tr>
        <tr>
          <th scope="row">Started</th>
          <td>{formatWhen(run.started_at)}</td>
        </tr>
        <tr>
          <th scope="row">Finished</th>
          <td>{formatWhen(run.finished_at, "Still running")}</td>
        </tr>
        {perSample || run.kind === "scenarios" || run.kind === "lens" ? null : (
          <tr>
            <th scope="row">Transcript</th>
            <td>
              {log}
              {error ? <div role="alert">{error}</div> : null}
            </td>
          </tr>
        )}
      </tbody>
    </table>
  );
}
