"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import agentStyles from "@/components/agents/agents.module.css";
import { StatusBadge } from "@/components/runs/Provenance";
import { Button, Card, Notice, formatWhen } from "@/components/ui";
import { launchWitness, type WitnessReaderOut, type WitnessRunSummary } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

import styles from "./ethos.module.css";

/** Witness runs on the same source as an Ethos run, and a way to start one. */
export function WitnessCard({
  sourceRunId,
  ethosRunId,
  runs,
  readers,
  canLaunch,
}: {
  sourceRunId: string;
  ethosRunId: string;
  runs: WitnessRunSummary[];
  readers: WitnessReaderOut[];
  canLaunch: boolean;
}) {
  const router = useRouter();
  const [reader, setReader] = useState(readers[0]?.key ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await launchWitness({
      client: browserClient,
      body: { source_run: sourceRunId, reader },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The witness could not be started.");
      return;
    }
    router.push(`/ethos/witness/${data.id}?ethos_run=${ethosRunId}`);
  }

  return (
    <Card title="Signals from an open model">
      <p className={styles.quiet}>
        An open-weight model reads the same conversations on the Droplet runner and reports
        per-token signals. Set beside these labels, they show where text and internals agree.
      </p>
      {runs.length ? (
        <table>
          <tbody>
            {runs.map((item) => (
              <tr key={item.run.id}>
                <td>
                  <Link href={`/ethos/witness/${item.run.id}?ethos_run=${ethosRunId}`}>
                    {item.reader.key}
                  </Link>{" "}
                  <span className={styles.quiet}>{item.reader.model}</span>
                </td>
                <td>
                  <StatusBadge status={item.run.status} />
                </td>
                <td>{formatWhen(item.run.created_at)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      ) : (
        <p>No open model has read this run yet.</p>
      )}
      {canLaunch ? (
        readers.length ? (
          <div className={agentStyles.inlineForm}>
            <label className={agentStyles.field}>
              Reader
              <select value={reader} onChange={(event) => setReader(event.target.value)}>
                {readers.map((item) => (
                  <option key={item.key} value={item.key}>
                    {item.key} ({item.model})
                  </option>
                ))}
              </select>
            </label>
            <Button onClick={start} disabled={busy || !reader}>
              Read with the open model
            </Button>
          </div>
        ) : (
          <p className={styles.quiet}>
            No witness reader is configured. Readers are set in config/witness.yaml and run on
            the Droplet runner.
          </p>
        )
      ) : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
    </Card>
  );
}
