"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";

import { DataTable } from "@/components/data/DataTable";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { Button, Card, Mono, Notice, Select, formatWhen } from "@/components/ui";
import { launchWitness, type WitnessReaderOut, type WitnessRunSummary } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

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
    const { data, error: failed } = await launchWitness({ client: browserClient, body: { source_run: sourceRunId, reader } });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The open model could not be started. Try again.");
      return;
    }
    router.push(`/ethos/witness/${data.id}?ethos_run=${ethosRunId}`);
  }

  return (
    <Card title="Signals from an open model">
      <p className="ag-quiet">
        An open-weight model reads the same conversations on the Droplet runner and reports per-token signals. Set
        beside these labels, they show where text and internals agree.
      </p>
      {runs.length ? (
        <DataTable
          density="dense"
          columns={[
            { key: "reader", label: "Reader" },
            { key: "status", label: "Status" },
            { key: "started", label: "Started" },
          ]}
          rows={runs.map((item) => ({
            id: item.run.id,
            cells: {
              reader: (
                <>
                  <Link href={`/ethos/witness/${item.run.id}?ethos_run=${ethosRunId}`}>{item.reader.key}</Link>{" "}
                  <Mono plain>{item.reader.model}</Mono>
                </>
              ),
              status: <StatusBadge status={item.run.status} />,
              started: formatWhen(item.run.created_at),
            },
          }))}
        />
      ) : (
        <p>No open model has read this run yet.</p>
      )}
      {canLaunch ? (
        readers.length ? (
          <div className="ag-form-row" style={{ marginTop: "var(--space-4)" }}>
            <Select
              label="Reader"
              value={reader}
              onChange={(event) => setReader(event.target.value)}
              options={readers.map((item) => ({ value: item.key, label: `${item.key} (${item.model})` }))}
            />
            <Button onClick={start} disabled={busy || !reader}>
              Read with the open model
            </Button>
          </div>
        ) : (
          <p className="ag-quiet">
            No Witness reader is configured. Readers are set in config/witness.yaml and run on the Droplet runner.
          </p>
        )
      ) : null}
      {error ? <Notice tone="danger">{error}</Notice> : null}
    </Card>
  );
}
