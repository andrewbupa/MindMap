"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { Heatmap } from "@/components/inquiry/Heatmap";
import { Provenance } from "@/components/runs/Provenance";
import { RunProgress } from "@/components/runs/RunProgress";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { Card, Checkbox, Field, LinkButton, Notice, PageHeader } from "@/components/ui";
import { readInquiryRun, type DimensionOut, type InquiryRunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

export function RunView({ run, dimensions }: { run: InquiryRunOut; dimensions: DimensionOut[] }) {
  const router = useRouter();
  const initial: Live = { status: run.run.status, tokens_used: run.run.tokens_used, counts: run.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/inquiry/runs/${run.run.id}/events`,
    poll: async () => {
      const { data } = await readInquiryRun({ client: browserClient, path: { run_id: run.run.id } });
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

  const [search, setSearch] = useState("");
  const [concerning, setConcerning] = useState(false);
  const [hideNoted, setHideNoted] = useState(false);
  const ours = dimensions.filter((d) => d.custom && d.palette !== "good-high").map((d) => d.name);
  const shown = run.transcripts.filter((t) => {
    if (search && !(t.scenario_key ?? "").toLowerCase().includes(search.trim().toLowerCase())) return false;
    if (concerning && !ours.some((name) => (t.scores[name] ?? 0) >= 7)) return false;
    if (hideNoted && t.content_notes.length) return false;
    return true;
  });

  const status = live?.status ?? run.run.status;
  const counts = live?.counts ?? run.counts;
  return (
    <>
      <PageHeader
        title={run.run.title}
        actions={
          OPEN.has(status) ? null : (
            <LinkButton href={`/ethos?source=${run.run.id}`}>Read these conversations with Ethos</LinkButton>
          )
        }
      >
        <p>
          <Link href={`/agents/${run.agent}/versions/${run.version}`}>
            {run.agent} {run.version}
          </Link>{" "}
          against {run.seeds.length} seeds. <StatusBadge status={status} />
        </p>
      </PageHeader>
      <Card title="Progress">
        <RunProgress counts={counts} />
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
      </Card>
      <Card title="Scores">
        <div className="ag-form-row" style={{ marginBottom: "var(--space-4)" }}>
          <Field
            label="Find a seed"
            type="search"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="declined-mri"
          />
          <Checkbox
            label="Only those scoring 7 or more on our dimensions"
            checked={concerning}
            onChange={(event) => setConcerning(event.target.checked)}
          />
          <Checkbox
            label="Hide those with content notes"
            checked={hideNoted}
            onChange={(event) => setHideNoted(event.target.checked)}
          />
        </div>
        <p className="ag-quiet">
          {shown.length} of {run.transcripts.length} transcripts, the most concerning first.
        </p>
        <Heatmap transcripts={shown} dimensions={dimensions} />
      </Card>
      <Card title="Run">
        <Provenance run={run.run} />
      </Card>
    </>
  );
}
