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
              Counted per model call{run.log_uri ? <>; each call is in the {log}</> : "."}
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
        <tr>
          <th scope="row">Transcript</th>
          <td>
            {log}
            {error ? <div role="alert">{error}</div> : null}
          </td>
        </tr>
      </tbody>
    </table>
  );
}
