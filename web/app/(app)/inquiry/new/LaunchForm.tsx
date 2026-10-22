"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { Fold } from "@/components/runs/Messages";
import { LaunchEstimate } from "@/components/runs/LaunchEstimate";
import { Badge, Button, Card, Checkbox, Field, LinkButton, Notice, Select, sentenceCase } from "@/components/ui";
import { launchInquiry, listSeeds, type AgentSummary, type SeedOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const ALL = "";

export function LaunchForm({ agents }: { agents: AgentSummary[] }) {
  const router = useRouter();
  const [agentKey, setAgentKey] = useState(agents[0]?.key ?? "");
  const agent = agents.find((item) => item.key === agentKey);
  const [version, setVersion] = useState(agent?.latest_version ?? "");
  const [seeds, setSeeds] = useState<SeedOut[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [tag, setTag] = useState(ALL);
  const [maxTurns, setMaxTurns] = useState(30);
  const [epochs, setEpochs] = useState(1);
  const [compaction, setCompaction] = useState(true);
  const [budget, setBudget] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    void listSeeds({ client: browserClient, query: { agent: agentKey } }).then(({ data }) => {
      if (cancelled || !data) return;
      setSeeds(data);
      setChosen(new Set(data.map((seed) => seed.key)));
    });
    return () => {
      cancelled = true;
    };
  }, [agentKey]);

  const tags = [...new Set(seeds.flatMap((seed) => seed.tags))].sort();
  const shown = seeds.filter((seed) => tag === ALL || seed.tags.includes(tag));

  function toggle(key: string) {
    setChosen((current) => {
      const next = new Set(current);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await launchInquiry({
      client: browserClient,
      body: { agent: agentKey, version, seeds: [...chosen], max_turns: maxTurns, epochs, compaction, token_budget: budget },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The audit could not be started. Check the choices and try again.");
      return;
    }
    router.push(`/inquiry/runs/${data.id}`);
  }

  const samples = chosen.size * epochs;
  const rows: Row[] = shown.map((seed) => ({
    id: seed.key,
    cells: {
      include: <Checkbox label={<span className="ag-sr">Include {seed.title}</span>} checked={chosen.has(seed.key)} onChange={() => toggle(seed.key)} />,
      seed: <Fold summary={seed.title}>{seed.text}</Fold>,
      tags: (
        <span className="ag-row">
          {seed.content_notes.map((note) => (
            <Badge key={note} tone="warn">
              Content note: {sentenceCase(note).toLowerCase()}
            </Badge>
          ))}
          {seed.tags.map((item) => (
            <Badge key={item}>{sentenceCase(item)}</Badge>
          ))}
        </span>
      ),
    },
    sort: { seed: seed.title },
  }));

  return (
    <div className="ag-form" style={{ maxWidth: "none" }}>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <Card title="What to audit">
        <div className="ag-form-row">
          <Select
            label="Agent"
            value={agentKey}
            onChange={(event) => {
              setAgentKey(event.target.value);
              const next = agents.find((item) => item.key === event.target.value);
              setVersion(next?.latest_version ?? "");
            }}
            options={agents.map((item) => ({ value: item.key, label: item.name }))}
          />
          <Select label="Prompt version" value={version} onChange={(event) => setVersion(event.target.value)} options={agent?.versions ?? []} />
          <Field label="Auditor turns" type="number" min={2} max={60} value={maxTurns} onChange={(event) => setMaxTurns(Number(event.target.value))} />
          <Field label="Repetitions" type="number" min={1} max={10} value={epochs} onChange={(event) => setEpochs(Number(event.target.value))} />
        </div>
        <div style={{ marginTop: "var(--space-4)" }}>
          <Checkbox
            label="Let Petri summarise long audits for the auditor (compaction)"
            checked={compaction}
            onChange={(event) => setCompaction(event.target.checked)}
          />
        </div>
      </Card>
      <Card
        title="Seeds"
        actions={
          <span className="ag-row">
            <LinkButton onClick={() => setChosen(new Set([...chosen, ...shown.map((seed) => seed.key)]))}>Choose all shown</LinkButton>
            <LinkButton onClick={() => setChosen(new Set([...chosen].filter((key) => !shown.some((seed) => seed.key === key))))}>
              Clear all shown
            </LinkButton>
          </span>
        }
      >
        <div className="ag-form-row" style={{ marginBottom: "var(--space-4)" }}>
          <Select
            label="Show seeds tagged"
            value={tag}
            onChange={(event) => setTag(event.target.value)}
            options={[{ value: ALL, label: "Any tag" }, ...tags.map((item) => ({ value: item, label: sentenceCase(item) }))]}
          />
          <p className="ag-quiet" style={{ margin: 0 }}>
            {chosen.size} of {seeds.length} seeds chosen.
          </p>
        </div>
        <DataTable
          density="dense"
          columns={[
            { key: "include", label: <span className="ag-sr">Include</span>, sortable: false },
            { key: "seed", label: "Seed" },
            { key: "tags", label: "Tags and content notes", sortable: false },
          ]}
          rows={rows}
        />
      </Card>
      <Card title="Cost and budget">
        <LaunchEstimate kind="inquiry" samples={samples} budget={budget} onBudget={setBudget} />
        <div style={{ marginTop: "var(--space-4)" }}>
          <Button onClick={start} disabled={busy || chosen.size === 0 || !version}>
            Start audit of {samples} {samples === 1 ? "sample" : "samples"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
