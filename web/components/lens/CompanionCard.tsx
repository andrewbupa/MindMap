"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import agentStyles from "@/components/agents/agents.module.css";
import { StatusBadge } from "@/components/runs/Provenance";
import { Button, Card, Notice, formatWhen } from "@/components/ui";
import { launchCompanion, type CompanionReaderOut, type CompanionRunSummary } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

import styles from "./lens.module.css";

/** Companion runs on the same source as a Lens run, and a way to start one. */
export function CompanionCard({
  sourceRunId,
  lensRunId,
  runs,
  readers,
  canLaunch,
}: {
  sourceRunId: string;
  lensRunId: string;
  runs: CompanionRunSummary[];
  readers: CompanionReaderOut[];
  canLaunch: boolean;
}) {
  const router = useRouter();
  const [reader, setReader] = useState(readers[0]?.key ?? "");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await launchCompanion({
      client: browserClient,
      body: { source_run: sourceRunId, reader },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The companion could not be started.");
      return;
    }
    router.push(`/lens/companion/${data.id}?lens_run=${lensRunId}`);
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
                  <Link href={`/lens/companion/${item.run.id}?lens_run=${lensRunId}`}>
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
            No companion reader is configured. Readers are set in config/companion.yaml and run on
            the Droplet runner.
          </p>
        )
      ) : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
    </Card>
  );
}
