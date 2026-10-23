"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { LaunchEstimate } from "@/components/runs/LaunchEstimate";
import { Button, Card, Checkbox, Field, Mono, Notice, Select } from "@/components/ui";
import { launchTally, type AgentSummary, type ScenarioSetSummary } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function SuiteForm({
  behaviour,
  scenarioSet,
  agents,
}: {
  behaviour: string;
  scenarioSet: ScenarioSetSummary;
  agents: AgentSummary[];
}) {
  const router = useRouter();
  const [agentKey, setAgentKey] = useState(agents[0]?.key ?? "");
  const agent = agents.find((item) => item.key === agentKey);
  const [versions, setVersions] = useState<Set<string>>(new Set(agent?.versions ?? []));
  const [epochs, setEpochs] = useState(3);
  const [maxTurns, setMaxTurns] = useState(15);
  const [compaction, setCompaction] = useState(true);
  const [budget, setBudget] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  function toggle(version: string) {
    setVersions((current) => {
      const next = new Set(current);
      if (next.has(version)) next.delete(version);
      else next.add(version);
      return next;
    });
  }

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await launchTally({
      client: browserClient,
      body: {
        agent: agentKey,
        versions: (agent?.versions ?? []).filter((v) => versions.has(v)),
        scenario_set: scenarioSet.id,
        epochs,
        max_turns: maxTurns,
        compaction,
        token_budget: budget,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The suite could not be started. Check the choices and try again.");
      return;
    }
    const [only] = data;
    router.push(data.length === 1 && only ? `/tally/runs/${only.id}` : `/tally/behaviours/${behaviour}`);
  }

  // Each prompt version runs as its own run, with its own budget.
  const perVersion = scenarioSet.scenario_count * epochs;
  const samples = versions.size * perVersion;
  return (
    <div className="ag-form" style={{ maxWidth: "none" }}>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <Card title="What to run">
        <p className="ag-quiet">
          Scenario set <Mono>{scenarioSet.content_hash.slice(0, 12)}</Mono>, with {scenarioSet.scenario_count} scenarios.
        </p>
        <div className="ag-form-row">
          <Select
            label="Agent"
            value={agentKey}
            onChange={(event) => {
              setAgentKey(event.target.value);
              const next = agents.find((item) => item.key === event.target.value);
              setVersions(new Set(next?.versions ?? []));
            }}
            options={agents.map((item) => ({ value: item.key, label: item.name }))}
          />
          <Field label="Repetitions" type="number" min={1} max={10} value={epochs} onChange={(event) => setEpochs(Number(event.target.value))} />
          <Field label="Auditor turns" type="number" min={2} max={60} value={maxTurns} onChange={(event) => setMaxTurns(Number(event.target.value))} />
        </div>
        <fieldset className="ag-fieldset" style={{ marginTop: "var(--space-4)" }}>
          <legend className="ag-label">Prompt versions</legend>
          <div className="ag-row">
            {(agent?.versions ?? []).map((version) => (
              <Checkbox key={version} label={version} checked={versions.has(version)} onChange={() => toggle(version)} />
            ))}
          </div>
        </fieldset>
        <div style={{ marginTop: "var(--space-4)" }}>
          <Checkbox
            label="Let Petri summarise long conversations for the auditor (compaction)"
            checked={compaction}
            onChange={(event) => setCompaction(event.target.checked)}
          />
        </div>
      </Card>
      <Card title="Cost and budget">
        <p className="ag-quiet">
          The estimate and the cap are for each prompt version: {perVersion} {perVersion === 1 ? "rollout" : "rollouts"}{" "}
          apiece.
        </p>
        <LaunchEstimate kind="tally" samples={perVersion} unit="rollout" budget={budget} onBudget={setBudget} />
        <div style={{ marginTop: "var(--space-4)" }}>
          <Button onClick={start} disabled={busy || versions.size === 0 || epochs < 1}>
            Start {samples} {samples === 1 ? "rollout" : "rollouts"}
          </Button>
        </div>
      </Card>
    </div>
  );
}
