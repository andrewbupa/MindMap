"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Field, Notice, Select } from "@/components/ui";
import { createGoldSet, type EthosSourceOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function CreateGoldSet({ sources }: { sources: EthosSourceOut[] }) {
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
    router.push(`/jury/gold/${data.id}`);
  }

  if (!sources.length) return <p>No finished runs to draw from yet.</p>;
  return (
    <div className="ag-form" style={{ maxWidth: "none" }}>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className="ag-form-row">
        <Field label="Name" value={name} onChange={(event) => setName(event.target.value)} hint="At least three characters." />
        <Select
          label="Draw from"
          value={source}
          onChange={(event) => setSource(event.target.value)}
          options={sources.map((item) => ({ value: item.run.id, label: `${item.run.title} (${item.transcripts})` }))}
        />
        <Field label="Transcripts" type="number" min={1} max={500} value={size} onChange={(e) => setSize(Number(e.target.value))} />
        <Field
          label="Seed"
          type="number"
          value={seed}
          onChange={(e) => setSeed(Number(e.target.value))}
          hint="The same seed draws the same transcripts."
        />
      </div>
      <div>
        <Button onClick={create} disabled={name.trim().length < 3 || !source}>
          Create gold set
        </Button>
      </div>
    </div>
  );
}
