"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import measureStyles from "@/components/measure/measure.module.css";
import { Button, Card, Mono, Notice } from "@/components/ui";
import { launchMeasure, type AgentSummary, type ScenarioSetSummary } from "@/lib/api";
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
    const { data, error: failed } = await launchMeasure({
      client: browserClient,
      body: {
        agent: agentKey,
        versions: (agent?.versions ?? []).filter((v) => versions.has(v)),
        scenario_set: scenarioSet.id,
        epochs,
        max_turns: maxTurns,
        compaction,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The suite could not be started.");
      return;
    }
    const [only] = data;
    router.push(data.length === 1 && only ? `/measure/runs/${only.id}` : `/measure/behaviours/${behaviour}`);
  }

  const samples = versions.size * scenarioSet.scenario_count * epochs;
  return (
    <Card>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <p>
        Scenario set <Mono>{scenarioSet.content_hash.slice(0, 12)}</Mono>, with{" "}
        {scenarioSet.scenario_count} scenarios.
      </p>
      <div className={styles.inlineForm}>
        <label className={styles.field}>
          Agent
          <select
            value={agentKey}
            onChange={(event) => {
              setAgentKey(event.target.value);
              const next = agents.find((item) => item.key === event.target.value);
              setVersions(new Set(next?.versions ?? []));
            }}
          >
            {agents.map((item) => (
              <option key={item.key} value={item.key}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Repetitions
          <input
            type="number"
            min={1}
            max={10}
            value={epochs}
            onChange={(event) => setEpochs(Number(event.target.value))}
          />
        </label>
        <label className={styles.field}>
          Auditor turns
          <input
            type="number"
            min={2}
            max={60}
            value={maxTurns}
            onChange={(event) => setMaxTurns(Number(event.target.value))}
          />
        </label>
      </div>
      <fieldset className={measureStyles.choices}>
        <legend>Prompt versions</legend>
        {(agent?.versions ?? []).map((version) => (
          <label key={version}>
            <input type="checkbox" checked={versions.has(version)} onChange={() => toggle(version)} />{" "}
            {version}{" "}
          </label>
        ))}
      </fieldset>
      <p>
        <label>
          <input
            type="checkbox"
            checked={compaction}
            onChange={(event) => setCompaction(event.target.checked)}
          />{" "}
          Let Petri summarise long conversations for the auditor (compaction)
        </label>
      </p>
      <p>
        <Button onClick={start} disabled={busy || versions.size === 0 || epochs < 1}>
          Start {samples} {samples === 1 ? "rollout" : "rollouts"}
        </Button>
      </p>
    </Card>
  );
}
