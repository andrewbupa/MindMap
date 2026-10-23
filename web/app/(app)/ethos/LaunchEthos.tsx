"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Notice, Select } from "@/components/ui";
import { launchEthos, type EthosSourceOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function LaunchEthos({ sources, initial }: { sources: EthosSourceOut[]; initial?: string }) {
  const router = useRouter();
  const [source, setSource] = useState(
    sources.find((s) => s.run.id === initial)?.run.id ?? sources[0]?.run.id ?? "",
  );
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const chosen = sources.find((s) => s.run.id === source);

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await launchEthos({ client: browserClient, body: { source_run: source } });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Ethos could not be started.");
      return;
    }
    router.push(`/ethos/runs/${data.id}`);
  }

  if (!sources.length) return <p>No finished runs to read yet. Run an audit or a suite first.</p>;
  return (
    <div className="ag-form">
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className="ag-form-row">
        <Select
          label="Run to read"
          value={source}
          onChange={(event) => setSource(event.target.value)}
          options={sources.map((item) => ({ value: item.run.id, label: `${item.run.title} (${item.transcripts} transcripts)` }))}
        />
        <Button onClick={start} disabled={busy || !source}>
          Read {chosen?.transcripts ?? 0} transcripts with the panel
        </Button>
      </div>
    </div>
  );
}
