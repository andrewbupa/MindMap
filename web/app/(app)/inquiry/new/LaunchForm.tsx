"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Badge, Button, Card, Notice, sentenceCase } from "@/components/ui";
import { launchInquiry, listSeeds, type AgentSummary, type SeedOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function LaunchForm({ agents }: { agents: AgentSummary[] }) {
  const router = useRouter();
  const [agentKey, setAgentKey] = useState(agents[0]?.key ?? "");
  const agent = agents.find((item) => item.key === agentKey);
  const [version, setVersion] = useState(agent?.latest_version ?? "");
  const [seeds, setSeeds] = useState<SeedOut[]>([]);
  const [chosen, setChosen] = useState<Set<string>>(new Set());
  const [maxTurns, setMaxTurns] = useState(30);
  const [epochs, setEpochs] = useState(1);
  const [compaction, setCompaction] = useState(true);
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
      body: {
        agent: agentKey,
        version,
        seeds: [...chosen],
        max_turns: maxTurns,
        epochs,
        compaction,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The audit could not be started.");
      return;
    }
    router.push(`/inquiry/runs/${data.id}`);
  }

  const samples = chosen.size * epochs;
  return (
    <Card>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className={styles.inlineForm}>
        <label className={styles.field}>
          Agent
          <select
            value={agentKey}
            onChange={(event) => {
              setAgentKey(event.target.value);
              const next = agents.find((item) => item.key === event.target.value);
              setVersion(next?.latest_version ?? "");
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
          Prompt version
          <select value={version} onChange={(event) => setVersion(event.target.value)}>
            {(agent?.versions ?? []).map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
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
      </div>
      <p>
        <label>
          <input
            type="checkbox"
            checked={compaction}
            onChange={(event) => setCompaction(event.target.checked)}
          />{" "}
          Let Petri summarise long audits for the auditor (compaction)
        </label>
      </p>
      <h3>Seeds</h3>
      <table>
        <thead>
          <tr>
            <th scope="col">
              <span className="visually-hidden">Include</span>
            </th>
            <th scope="col">Seed</th>
            <th scope="col">Tags</th>
          </tr>
        </thead>
        <tbody>
          {seeds.map((seed) => (
            <tr key={seed.key}>
              <td>
                <input
                  type="checkbox"
                  aria-label={`Include ${seed.title}`}
                  checked={chosen.has(seed.key)}
                  onChange={() => toggle(seed.key)}
                />
              </td>
              <td>
                <details>
                  <summary>{seed.title}</summary>
                  <p>{seed.text}</p>
                </details>
              </td>
              <td>
                {seed.content_notes.map((note) => (
                  <Badge key={note} tone="warn">
                    Content note: {sentenceCase(note)}
                  </Badge>
                ))}
                {seed.tags.map((tag) => (
                  <Badge key={tag}>{sentenceCase(tag)}</Badge>
                ))}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      <p>
        <Button onClick={start} disabled={busy || chosen.size === 0 || !version}>
          Start audit of {samples} {samples === 1 ? "sample" : "samples"}
        </Button>
      </p>
    </Card>
  );
}
