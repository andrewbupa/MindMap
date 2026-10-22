"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";

import { WitnessCard } from "@/components/ethos/WitnessCard";
import { ETHOS_QUIET, familyColour, formatMedian, labelName } from "@/components/ethos/family";
import styles from "@/components/ethos/ethos.module.css";
import { Provenance } from "@/components/runs/Provenance";
import runStyles from "@/components/runs/runs.module.css";
import { Badge, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import {
  readEthosRun,
  type WitnessReaderOut,
  type WitnessRunSummary,
  type EthosRunOut,
  type EthosRunSummary,
} from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "Not read" : `${Math.round(value * 100)}%`;
}

/** A share and its 95% interval on a 0 to 100% track. */
function IntervalBar({ share, low, high }: { share: number | null | undefined; low?: number; high?: number }) {
  if (share === null || share === undefined || low === undefined || high === undefined) return null;
  const x = (value: number) => 4 + value * 132;
  return (
    <svg className={styles.interval} viewBox="0 0 140 14" aria-hidden="true">
      <line x1={4} x2={136} y1={7} y2={7} stroke="var(--color-chart-grid)" />
      <line x1={x(low)} x2={x(high)} y1={7} y2={7} stroke="var(--color-text-muted)" strokeWidth={2} />
      <circle cx={x(share)} cy={7} r={4} fill="var(--color-chart-1)" stroke="var(--color-surface)" strokeWidth={2} />
    </svg>
  );
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
  const total = Object.values(counts).reduce((sum, n) => sum + n, 0);
  const families = [...new Set(run.labels.map((l) => l.family))];
  return (
    <>
      <PageHeader title={run.run.title} note={ETHOS_QUIET}>
        <p>
          The panel ({run.judges.join(" and ")}) read {run.transcripts.length} conversations from{" "}
          {run.source.title}, with taxonomy {run.run.taxonomy_version}.
        </p>
      </PageHeader>
      <Card title="Progress">
        <div className={runStyles.counts}>
          {Object.entries(counts).map(([status, n]) => (
            <Badge key={status}>
              {sentenceCase(status)}: {n}
            </Badge>
          ))}
          <span className={runStyles.quiet}>{total} conversations in all.</span>
        </div>
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
      </Card>
      <Card title="Labels across every reply">
        <p className={styles.quiet}>
          A reply expresses a label when the panel&apos;s median intensity is 1 or more. Intervals
          are 95% Wilson intervals. Mean fit: {percent(run.mean_fit)}.
        </p>
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Label</th>
              <th scope="col">Replies expressing it</th>
              <th scope="col">Share</th>
              <th scope="col">
                <span className="visually-hidden">Interval</span>
              </th>
              <th scope="col">Mean intensity</th>
              <th scope="col">Disputed</th>
            </tr>
          </thead>
          {families.map((family) => (
            <tbody key={family}>
              <tr>
                <th scope="rowgroup" colSpan={6}>
                  <span className={styles.swatch} style={{ background: familyColour(family) }} />
                  {sentenceCase(family)}
                </th>
              </tr>
              {run.labels
                .filter((l) => l.family === family)
                .map((item) => (
                  <tr key={item.label}>
                    <td>
                      <Link href={`/ethos/taxonomy#${item.label}`}>{labelName(item.label)}</Link>{" "}
                      {item.trust_status !== "unrated" ? <Badge>{sentenceCase(item.trust_status)}</Badge> : null}
                    </td>
                    <td>
                      <Link href={`?label=${item.label}#evidence`}>
                        {item.expressed} of {item.replies}
                      </Link>
                    </td>
                    <td>
                      {percent(item.share)}
                      {item.interval
                        ? ` (${percent(item.interval.low)} to ${percent(item.interval.high)})`
                        : ""}
                    </td>
                    <td>
                      <IntervalBar share={item.share} low={item.interval?.low} high={item.interval?.high} />
                    </td>
                    <td>{formatMedian(Number(item.mean_intensity.toFixed(2)))}</td>
                    <td>
                      {item.disputed ? (
                        <Link href={`?label=${item.label}#evidence`}>{item.disputed}</Link>
                      ) : (
                        0
                      )}
                    </td>
                  </tr>
                ))}
            </tbody>
          ))}
        </table>
      </Card>
      {label ? (
        <Card title={`Findings for ${labelName(label).toLowerCase()}`}>
          <div id="evidence">
            {run.evidence.length === 0 ? <p>No judge found this label.</p> : null}
            <ul>
              {run.evidence.map((item) => (
                <li key={item.id}>
                  <Link href={`/ethos/runs/${run.run.id}/transcripts/${item.transcript_id}#a-${item.id}`}>
                    &ldquo;{item.quote}&rdquo;
                  </Link>{" "}
                  <span className={styles.quiet}>
                    intensity {item.intensity}, {item.judge}
                    {item.channel === "thinking_summary" ? ", in a thinking summary" : ""}
                  </span>
                </li>
              ))}
            </ul>
            <p>
              <Link href="?#evidence">Hide these findings</Link>
            </p>
          </div>
        </Card>
      ) : null}
      <Card title="Conversations">
        <table id="transcripts" className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">Repetition</th>
              <th scope="col">Replies</th>
              <th scope="col">Fit</th>
              <th scope="col">Disputed labels</th>
            </tr>
          </thead>
          <tbody>
            {run.transcripts.map((t) => (
              <tr key={t.transcript_id}>
                <td>
                  <Link href={`/ethos/runs/${run.run.id}/transcripts/${t.transcript_id}`}>
                    {sentenceCase((t.scenario_key ?? "Conversation").split("/").pop()!.replaceAll(/[-_]/g, " "))}
                  </Link>
                  {t.content_notes.map((note) => (
                    <Badge key={note} tone="warn">
                      Content note: {sentenceCase(note)}
                    </Badge>
                  ))}
                </td>
                <td>{t.epoch}</td>
                <td>{t.replies}</td>
                <td>{t.fit === null || t.fit === undefined ? "No profile" : percent(t.fit)}</td>
                <td>{t.disputed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Judges">
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Judge</th>
              <th scope="col">Findings kept</th>
              <th scope="col">Dropped</th>
            </tr>
          </thead>
          <tbody>
            {run.judge_counts.map((judge) => (
              <tr key={judge.judge}>
                <td>{judge.judge}</td>
                <td>{judge.kept}</td>
                <td>
                  {judge.dropped}
                  {run.dropped
                    .filter((d) => d.judge === judge.judge)
                    .map((d) => (
                      <div key={d.reason} className={styles.quiet}>
                        {d.count} {d.reason.replaceAll("_", " ")}
                      </div>
                    ))}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      {others.length ? (
        <Card title="Compare with another Ethos run">
          <p>
            <select value={other} onChange={(event) => setOther(event.target.value)} aria-label="Ethos run to compare">
              {others.map((o) => (
                <option key={o.run.id} value={o.run.id}>
                  {o.run.title}
                </option>
              ))}
            </select>{" "}
            <Link href={`/ethos/compare?a=${run.run.id}&b=${other}`}>Compare</Link>
          </p>
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
