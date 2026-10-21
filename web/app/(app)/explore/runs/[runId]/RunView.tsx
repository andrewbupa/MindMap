"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import styles from "@/components/runs/runs.module.css";
import { Provenance } from "@/components/runs/Provenance";
import { Badge, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readExploreRun, type DimensionOut, type ExploreRunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

import { Heatmap } from "./Heatmap";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

export function RunView({ run, dimensions }: { run: ExploreRunOut; dimensions: DimensionOut[] }) {
  const router = useRouter();
  const initial: Live = { status: run.run.status, tokens_used: run.run.tokens_used, counts: run.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/explore/runs/${run.run.id}/events`,
    poll: async () => {
      const { data } = await readExploreRun({ client: browserClient, path: { run_id: run.run.id } });
      return data ? { status: data.run.status, tokens_used: data.run.tokens_used, counts: data.counts } : null;
    },
    done: (value) => !OPEN.has(value.status),
    initial,
  });
  const seen = useRef(JSON.stringify(initial));
  useEffect(() => {
    const next = JSON.stringify(live);
    if (live && next !== seen.current) {
      seen.current = next;
      router.refresh();
    }
  }, [live, router]);

  const counts = live?.counts ?? run.counts;
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  return (
    <>
      <PageHeader title={run.run.title}>
        <p>
          <Link href={`/agents/${run.agent}/versions/${run.version}`}>
            {run.agent} {run.version}
          </Link>{" "}
          against {run.seeds.length} seeds.
        </p>
      </PageHeader>
      <Card title="Progress">
        <div className={styles.counts}>
          {Object.entries(counts).map(([status, n]) => (
            <Badge key={status}>
              {sentenceCase(status)}: {n}
            </Badge>
          ))}
          <span className={styles.quiet}>{total} samples in all.</span>
        </div>
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
      </Card>
      <Card title="Scores">
        <Heatmap transcripts={run.transcripts} dimensions={dimensions} />
      </Card>
      <Card title="Run">
        <Provenance run={run.run} />
      </Card>
    </>
  );
}
