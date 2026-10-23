"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Card, Notice, Select, TextArea } from "@/components/ui";
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
      <div className="ag-form" style={{ maxWidth: "none" }}>
        {error ? <Notice tone="danger">{error}</Notice> : null}
        <div className="ag-form-row">
          <Select label="Prompt version" value={version} onChange={(event) => setVersion(event.target.value)} options={agent.versions} />
          <Select
            label="Persona to play (optional)"
            value={persona}
            onChange={(event) => setPersona(event.target.value)}
            options={[{ value: "", label: "None" }, ...agent.personas.map((item) => ({ value: item.key, label: item.name }))]}
          />
          <Select
            label="Mode"
            value={mode}
            onChange={(event) => setMode(event.target.value as "deployed" | "open")}
            options={[
              { value: "deployed", label: "Deployed: our prompt and tools" },
              { value: "open", label: "Open: your own system prompt, no tools" },
            ]}
          />
        </div>
        {chosen ? (
          <Notice title={`Playing ${chosen.name}`}>
            {profile.summary} {profile.situation} The agent does not see this note. It is for you, as the person in the
            chat.
          </Notice>
        ) : null}
        {mode === "deployed" ? (
          <TextArea
            label="Context from connected systems (optional)"
            value={context}
            onChange={(event) => setContext(event.target.value)}
            placeholder="For example: Signed-in member: TEST-100231"
            hint="Added after the agent’s prompt in a clearly marked block."
          />
        ) : (
          <TextArea
            label="System prompt"
            value={systemPrompt}
            onChange={(event) => setSystemPrompt(event.target.value)}
            hint="Open mode tests the underlying model, not the agent we deploy."
          />
        )}
        <div>
          <Button onClick={start} disabled={busy}>
            Start conversation
          </Button>
        </div>
      </div>
    </Card>
  );
}
