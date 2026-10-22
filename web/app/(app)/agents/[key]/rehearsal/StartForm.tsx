"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Button, Card, Notice } from "@/components/ui";
import { startConversation, type AgentDetail } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function StartForm({ agent, initialVersion }: { agent: AgentDetail; initialVersion: string }) {
  const router = useRouter();
  const [version, setVersion] = useState(initialVersion);
  const [persona, setPersona] = useState("");
  const [mode, setMode] = useState<"deployed" | "open">("deployed");
  const [context, setContext] = useState("");
  const [systemPrompt, setSystemPrompt] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const chosen = agent.personas.find((item) => item.key === persona);
  const profile = (chosen?.profile ?? {}) as { summary?: string; situation?: string };

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await startConversation({
      client: browserClient,
      body: {
        agent: agent.key,
        version,
        persona: persona || null,
        mode,
        context: mode === "deployed" ? context || null : null,
        system_prompt: mode === "open" ? systemPrompt || null : null,
      },
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The conversation could not be started.");
      return;
    }
    router.push(`/rehearsal/${data.run.id}`);
  }

  return (
    <Card>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <div className={styles.inlineForm}>
        <label className={styles.field}>
          Prompt version
          <select value={version} onChange={(event) => setVersion(event.target.value)}>
            {agent.versions.map((item) => (
              <option key={item}>{item}</option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Persona to play (optional)
          <select value={persona} onChange={(event) => setPersona(event.target.value)}>
            <option value="">None</option>
            {agent.personas.map((item) => (
              <option key={item.key} value={item.key}>
                {item.name}
              </option>
            ))}
          </select>
        </label>
        <label className={styles.field}>
          Mode
          <select
            value={mode}
            onChange={(event) => setMode(event.target.value as "deployed" | "open")}
          >
            <option value="deployed">Deployed: our prompt and tools</option>
            <option value="open">Open: your own system prompt, no tools</option>
          </select>
        </label>
      </div>
      {chosen ? (
        <Notice>
          <strong>Playing {chosen.name}.</strong> {profile.summary} {profile.situation}
          <br />
          <small>The agent does not see this note. It is for you, as the person in the chat.</small>
        </Notice>
      ) : null}
      {mode === "deployed" ? (
        <label className={styles.field}>
          Context from connected systems (optional)
          <textarea
            value={context}
            onChange={(event) => setContext(event.target.value)}
            placeholder="For example: Signed-in member: TEST-100231"
          />
          <small>Added after the agent&apos;s prompt in a clearly marked block.</small>
        </label>
      ) : (
        <label className={styles.field}>
          System prompt
          <textarea
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
          />
          <small>Open mode tests the underlying model, not the agent we deploy.</small>
        </label>
      )}
      <p>
        <Button onClick={start} disabled={busy}>
          Start conversation
        </Button>
      </p>
    </Card>
  );
}
