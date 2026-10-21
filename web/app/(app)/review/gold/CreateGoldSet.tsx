"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Button, Notice } from "@/components/ui";
import { createGoldSet, type LensSourceOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function CreateGoldSet({ sources }: { sources: LensSourceOut[] }) {
  const router = useRouter();
  const [name, setName] = useState("");
  const [source, setSource] = useState(sources[0]?.run.id ?? "");
  const [size, setSize] = useState(60);
  const [seed, setSeed] = useState(0);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    const { data, error: failed } = await createGoldSet({
      client: browserClient,
      body: { name, source_run: source, size, seed },
    });
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The gold set could not be created.");
      return;
    }
    router.push(`/review/gold/${data.id}`);
  }

  if (!sources.length) return <p>No finished runs to draw from yet.</p>;
  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className={styles.inlineForm}>
        <label className={styles.field}>
          Name
          <input value={name} onChange={(event) => setName(event.target.value)} />
        </label>
        <label className={styles.field}>
          Draw from
          <select value={source} onChange={(event) => setSource(event.target.value)}>
            {sources.map((item) => (
              <option key={item.run.id} value={item.run.id}>
                {item.run.title} ({item.transcripts})
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Transcripts
          <input type="number" min={1} max={500} value={size} onChange={(e) => setSize(Number(e.target.value))} />
        </label>
        <label className={styles.field}>
          Seed
          <input type="number" value={seed} onChange={(e) => setSeed(Number(e.target.value))} />
        </label>
      </div>
      <p>
        <Button onClick={create} disabled={name.trim().length < 3 || !source}>
          Create gold set
        </Button>
      </p>
    </div>
  );
}
