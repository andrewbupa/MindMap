"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { IntervalBar } from "@/components/data/IntervalBar";
import { ETHOS_NOTE, formatMedian, labelName } from "@/components/ethos/family";
import { LabelChip, TrustBadge } from "@/components/ethos/LabelChip";
import { WitnessCard } from "@/components/ethos/WitnessCard";
import { Provenance } from "@/components/runs/Provenance";
import { RunProgress } from "@/components/runs/RunProgress";
import { Badge, ButtonLink, Card, Mono, Notice, PageHeader, Select, sentenceCase } from "@/components/ui";
import {
  readEthosRun,
  type EthosRunOut,
  type EthosRunSummary,
  type WitnessReaderOut,
  type WitnessRunSummary,
} from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not read" : `${Math.round(value * 100)}%`;
}

export function EthosRunView({
  run,
  label,
  others,
  witness,
}: {
  run: EthosRunOut;
  label: string | null;
  others: EthosRunSummary[];
  witness: { runs: WitnessRunSummary[]; readers: WitnessReaderOut[]; canLaunch: boolean };
}) {
  const router = useRouter();
  const initial: Live = { status: run.run.status, tokens_used: run.run.tokens_used, counts: run.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/ethos/runs/${run.run.id}/events`,
    poll: async () => {
      const { data } = await readEthosRun({ client: browserClient, path: { run_id: run.run.id } });
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
  const [other, setOther] = useState(others[0]?.run.id ?? "");

  const counts = live?.counts ?? run.counts;
  const labelRows: Row[] = run.labels.map((item) => ({
    id: item.label,
    cells: {
      label: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          <Link href={`/ethos/taxonomy#${item.label}`} style={{ textDecoration: "none" }}>
            <LabelChip family={item.family} label={item.label} />
          </Link>
          <TrustBadge trust={item.trust_status} />
        </span>
      ),
      expressed: (
        <Link href={`?label=${item.label}#evidence`}>
          {item.expressed} of {item.replies}
        </Link>
      ),
      share:
        item.share !== null && item.share !== undefined && item.interval ? (
          <IntervalBar
            value={item.share}
            low={item.interval.low}
            high={item.interval.high}
            family={item.family}
            label={labelName(item.label)}
          />
        ) : (
          percent(item.share)
        ),
      intensity: formatMedian(Number(item.mean_intensity.toFixed(2))),
      disputed: item.disputed ? <Link href={`?label=${item.label}#evidence`}>{item.disputed}</Link> : "0",
    },
    sort: {
      label: item.label,
      expressed: item.expressed,
      share: item.share,
      intensity: item.mean_intensity,
      disputed: item.disputed,
    },
  }));
  const conversationRows: Row[] = run.transcripts.map((t) => ({
    id: t.transcript_id,
    cells: {
      scenario: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          <Link href={`/ethos/runs/${run.run.id}/transcripts/${t.transcript_id}`}>
            {sentenceCase((t.scenario_key ?? "Conversation").split("/").pop()!.replaceAll(/[-_]/g, " "))}
          </Link>
          {t.content_notes.map((note) => (
            <Badge key={note} tone="warn">
              Content note: {sentenceCase(note).toLowerCase()}
            </Badge>
          ))}
        </span>
      ),
      epoch: t.epoch,
      replies: t.replies,
      fit: t.fit === null || t.fit === undefined ? <span className="ag-muted">No profile</span> : percent(t.fit),
      disputed: t.disputed,
    },
    sort: { scenario: t.scenario_key, epoch: t.epoch, replies: t.replies, fit: t.fit, disputed: t.disputed },
  }));
  return (
    <>
      <PageHeader title={run.run.title} note={ETHOS_NOTE}>
        <p>
          The panel ({run.judges.join(" and ")}) read {run.transcripts.length} conversations from {run.source.title},
          with taxonomy <Mono>{run.run.taxonomy_version ?? ""}</Mono>. Mean fit: {percent(run.mean_fit)}.
        </p>
      </PageHeader>
      <Card title="Progress">
        <RunProgress counts={counts} unit="conversations" />
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
      </Card>
      <Card title="Labels across every reply">
        <p className="ag-quiet">
          A reply expresses a label when the panel&apos;s median intensity is 1 or more. The track shows each share with
          its 95% Wilson interval. Each count opens the findings behind it.
        </p>
        <DataTable
          columns={[
            { key: "label", label: "Label" },
            { key: "expressed", label: "Replies expressing it", align: "right" },
            { key: "share", label: "Share, with 95% interval" },
            { key: "intensity", label: "Mean intensity", align: "right" },
            { key: "disputed", label: "Disputed", align: "right" },
          ]}
          rows={labelRows}
        />
      </Card>
      {label ? (
        <Card
          id="evidence"
          title={`Findings for ${labelName(label).toLowerCase()}`}
          actions={<Link href="?#evidence">Hide these findings</Link>}
        >
          {run.evidence.length === 0 ? <p>No judge found this label.</p> : null}
          <ul className="ag-judges">
            {run.evidence.map((item) => (
              <li key={item.id} className="ag-judge">
                <Link href={`/ethos/runs/${run.run.id}/transcripts/${item.transcript_id}#a-${item.id}`}>
                  &ldquo;{item.quote}&rdquo;
                </Link>
                <span className="ag-muted">
                  Intensity {item.intensity}, <Mono plain>{item.judge}</Mono>
                  {item.channel === "thinking_summary" ? ", in a thinking summary" : ""}
                </span>
              </li>
            ))}
          </ul>
        </Card>
      ) : null}
      <Card title="Conversations">
        <DataTable
          columns={[
            { key: "scenario", label: "Scenario" },
            { key: "epoch", label: "Repetition", align: "right" },
            { key: "replies", label: "Replies", align: "right" },
            { key: "fit", label: "Fit", align: "right" },
            { key: "disputed", label: "Disputed labels", align: "right" },
          ]}
          rows={conversationRows}
          initialSort={{ key: "fit", dir: "asc" }}
        />
      </Card>
      <Card title="Judges">
        <DataTable
          columns={[
            { key: "judge", label: "Judge" },
            { key: "kept", label: "Findings kept", align: "right" },
            { key: "dropped", label: "Dropped", align: "right" },
          ]}
          rows={run.judge_counts.map((judge) => ({
            id: judge.judge,
            cells: {
              judge: <Mono plain>{judge.judge}</Mono>,
              kept: judge.kept,
              dropped: (
                <>
                  {judge.dropped}
                  {run.dropped
                    .filter((d) => d.judge === judge.judge)
                    .map((d) => (
                      <div key={d.reason} className="ag-muted">
                        {d.count} {d.reason.replaceAll("_", " ")}
                      </div>
                    ))}
                </>
              ),
            },
          }))}
        />
      </Card>
      {others.length ? (
        <Card title="Compare with another Ethos run">
          <div className="ag-form-row">
            <Select
              label="Ethos run to compare"
              value={other}
              onChange={(event) => setOther(event.target.value)}
              options={others.map((o) => ({ value: o.run.id, label: o.run.title }))}
            />
            <ButtonLink variant="secondary" href={`/ethos/compare?a=${run.run.id}&b=${other}`}>
              Compare
            </ButtonLink>
          </div>
        </Card>
      ) : null}
      <WitnessCard
        sourceRunId={run.source.id}
        ethosRunId={run.run.id}
        runs={witness.runs}
        readers={witness.readers}
        canLaunch={witness.canLaunch}
      />
      <Card title="Run">
        <Provenance run={run.run} />
      </Card>
    </>
  );
}
