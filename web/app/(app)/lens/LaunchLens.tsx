"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Button, Notice } from "@/components/ui";
import { launchLens, type LensSourceOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function LaunchLens({ sources, initial }: { sources: LensSourceOut[]; initial?: string }) {
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
    const { data, error: failed } = await launchLens({ client: browserClient, body: { source_run: source } });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Lens could not be started.");
      return;
    }
    router.push(`/lens/runs/${data.id}`);
  }

  if (!sources.length) return <p>No finished runs to read yet. Run an audit or a suite first.</p>;
  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className={styles.inlineForm}>
        <label className={styles.field}>
          Run to read
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            {sources.map((item) => (
              <option key={item.run.id} value={item.run.id}>
                {item.run.title} ({item.transcripts} transcripts)
              </option>
            ))}
          </select>
        </label>
      </div>
      <p>
        <Button onClick={start} disabled={busy || !source}>
          Read {chosen?.transcripts ?? 0} transcripts with the panel
        </Button>
      </p>
    </div>
  );
}
