"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { StatusBadge } from "@/components/runs/StatusBadge";
import { Button, Notice, formatNumber } from "@/components/ui";
import { generateScenarioSet, readBehaviour, type RunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

/** Start Bloom's scenario generation, and follow it until the scenario set is stored. */
export function GenerationPanel({
  behaviour,
  generating,
  canGenerate,
  hasCurrent,
}: {
  behaviour: string;
  generating: RunOut | null;
  canGenerate: boolean;
  hasCurrent: boolean;
}) {
  const router = useRouter();
  const [run, setRun] = useState<RunOut | null>(generating);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const live = useLiveStatus<Live>({
    streamUrl: run ? `/api/tally/runs/${run.id}/events` : null,
    poll: async () => {
      const { data } = await readBehaviour({ client: browserClient, path: { key: behaviour } });
      const found = data?.generations.find((item) => item.id === run?.id);
      return found ? { status: found.status, tokens_used: found.tokens_used, counts: {} } : null;
    },
    done: (value) => !OPEN.has(value.status),
    initial: run ? { status: run.status, tokens_used: run.tokens_used, counts: {} } : null,
  });
  const finished = live !== null && !OPEN.has(live.status);

  useEffect(() => {
    if (finished) router.refresh();
  }, [finished, router]);

  async function start() {
    setBusy(true);
    setError(null);
    const { data, error: failed } = await generateScenarioSet({
      client: browserClient,
      path: { key: behaviour },
      body: {},
    });
    setBusy(false);
    if (!data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "Generation could not be started.");
      return;
    }
    setRun(data);
  }

  const running = run !== null && !finished;
  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {running && live ? (
        <p>
          Generating scenarios: <StatusBadge status={live.status} />{" "}
          {live.tokens_used ? `${formatNumber(live.tokens_used)} tokens so far.` : null}{" "}
          Bloom writes its understanding of the behaviour, then the scenarios and their variations.
        </p>
      ) : null}
      {canGenerate && !running ? (
        <p>
          <Button onClick={start} disabled={busy} variant={hasCurrent ? "secondary" : "primary"}>
            {hasCurrent ? "Generate a new scenario set" : "Generate scenarios"}
          </Button>
        </p>
      ) : null}
    </div>
  );
}
