"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { SIGNAL_KINDS, labelName } from "@/components/ethos/family";
import { LabelChip, TrustBadge } from "@/components/ethos/LabelChip";
import { Provenance } from "@/components/runs/Provenance";
import { RunProgress } from "@/components/runs/RunProgress";
import { Card, Mono, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readWitnessRun, type WitnessRunOut, type ReplyRefOut, type SignalAgreementOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };
type Cell = "both" | "ethos_only" | "witness_only" | "neither";

const OPEN = new Set(["queued", "running"]);
const CELLS: { key: Cell; name: string }[] = [
  { key: "both", name: "Both" },
  { key: "ethos_only", name: "Ethos only" },
  { key: "witness_only", name: "Signal only" },
  { key: "neither", name: "Neither" },
];
const QUIET =
  "Signals from an open-weight model reading the text. They show how that model represents the conversation, not the agent's own internals.";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "None to compare" : `${Math.round(value * 100)}%`;
}

export function WitnessRunView({ data }: { data: WitnessRunOut }) {
  const router = useRouter();
  const initial: Live = { status: data.run.status, tokens_used: data.run.tokens_used, counts: data.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/witness/runs/${data.run.id}/events`,
    poll: async () => {
      const { data: next } = await readWitnessRun({ client: browserClient, path: { run_id: data.run.id } });
      return next ? { status: next.run.status, tokens_used: next.run.tokens_used, counts: next.counts } : null;
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

  const counts = live?.counts ?? data.counts;
  const waiting = (counts.queued ?? 0) > 0 && !(counts.running ?? 0);
  const ethos = data.ethos_run;
  const transcripts = (data.run.config.transcripts as string[]).length;

  function replyHref(reply: ReplyRefOut): string {
    return `/ethos/runs/${ethos?.id}/transcripts/${reply.transcript_id}?witness=${data.run.id}#r-${reply.message_id}`;
  }

  function replyName(reply: ReplyRefOut): string {
    const scenario = (reply.scenario_key ?? "Conversation").split("/").pop() ?? "Conversation";
    const repetition = reply.epoch > 1 ? `, repetition ${reply.epoch}` : "";
    return `${sentenceCase(scenario.replaceAll("-", " ").replaceAll("_", " "))}${repetition}, message ${reply.index + 1}`;
  }

  function cellId(agreement: SignalAgreementOut, cell: Cell): string {
    return `cell-${agreement.signal}-${cell}`;
  }

  return (
    <>
      <PageHeader title={data.run.title} note={QUIET}>
        <p>
          <Mono plain>{data.reader.model}</Mono> read {transcripts} conversations from{" "}
          {ethos ? <Link href={`/ethos/runs/${ethos.id}`}>{data.source.title}</Link> : data.source.title} with
          the reader {data.reader.key}, version {data.reader.version}.
        </p>
      </PageHeader>
      <Card title="Progress">
        <RunProgress counts={counts} unit="conversations" />
        {waiting ? (
          <p className="ag-quiet">
            Witness jobs wait on the witness queue until the Droplet runner takes them. If they stay
            queued, check the runner (see the runbook).
          </p>
        ) : null}
        {data.run.error ? <Notice tone="danger">{data.run.error}</Notice> : null}
        {Object.keys(data.dropped).length ? (
          <p className="ag-quiet">
            Signals dropped by the checks:{" "}
            {Object.entries(data.dropped)
              .map(([reason, n]) => `${n} (${reason.replaceAll("_", " ")})`)
              .join("; ")}
            . They count nowhere.
          </p>
        ) : null}
      </Card>
      <Card title="Signals beside Ethos labels">
        {!ethos ? (
          <p>
            No finished Ethos run reads {data.source.title}, so there is nothing to compare yet.{" "}
            <Link href={`/ethos?source=${data.source.id}`}>Read it with Ethos</Link>.
          </p>
        ) : (
          <>
            <p className="ag-quiet">
              Compared with <Link href={`/ethos/runs/${ethos.id}`}>{ethos.title}</Link>, over the replies both
              read. Ethos counts a label when the panel&apos;s median intensity is 1 or more; a signal counts
              when any token reaches its threshold. Each count opens its replies.
            </p>
            {data.ethos_runs.length > 1 ? (
              <p>
                Other Ethos runs on this source:{" "}
                {data.ethos_runs
                  .filter((r) => r.id !== ethos.id)
                  .map((r, i) => (
                    <span key={r.id}>
                      {i ? ", " : ""}
                      <Link href={`/ethos/witness/${data.run.id}?ethos_run=${r.id}`}>{r.title}</Link>
                    </span>
                  ))}
              </p>
            ) : null}
            {data.agreements.length === 0 ? (
              <p>None of this reader&apos;s signals is tied to an Ethos label.</p>
            ) : (
              <div className="ag-table-wrap"><table className="ag-table">
                <thead>
                  <tr>
                    <th scope="col">Signal</th>
                    <th scope="col">Ethos label</th>
                    {CELLS.map((cell) => (
                      <th key={cell.key} scope="col">
                        {cell.name}
                      </th>
                    ))}
                    <th scope="col">Agree</th>
                    <th scope="col">Both, when either flags</th>
                  </tr>
                </thead>
                <tbody>
                  {data.agreements.map((a) => (
                    <tr key={a.signal}>
                      <th scope="row">
                        {labelName(a.signal)}
                        <div className="ag-quiet">{SIGNAL_KINDS[a.kind] ?? a.kind}</div>
                      </th>
                      <td>
                        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
                          <Link href={`/ethos/runs/${ethos.id}?label=${a.label}`} style={{ textDecoration: "none" }}>
                            <LabelChip family={a.family} label={a.label} />
                          </Link>
                          {a.trust_status ? <TrustBadge trust={a.trust_status} /> : null}
                        </span>
                      </td>
                      {CELLS.map((cell) => (
                        <td key={cell.key}>
                          <a href={`#${cellId(a, cell.key)}`}>{a[cell.key].length}</a>
                        </td>
                      ))}
                      <td>
                        <a href={`#signal-${a.signal}`}>{percent(a.agreement)}</a>
                      </td>
                      <td>
                        <a href={`#signal-${a.signal}`}>{percent(a.positive)}</a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table></div>
            )}
          </>
        )}
      </Card>
      {ethos
        ? data.agreements.map((a) => (
            <div key={a.signal} id={`signal-${a.signal}`}>
              <Card title={`${labelName(a.signal)} beside ${labelName(a.label).toLowerCase()}`}>
                <p className="ag-quiet">
                  {a.replies} replies. They agree on {a.both.length + a.neither.length} ({percent(a.agreement)}).
                  Of the {a.both.length + a.ethos_only.length + a.witness_only.length} that either flags,
                  both flag {a.both.length} ({percent(a.positive)}).
                </p>
                {CELLS.map((cell) => (
                  <section key={cell.key} id={cellId(a, cell.key)}>
                    <h3>
                      {cell.name}: {a[cell.key].length} {a[cell.key].length === 1 ? "reply" : "replies"}
                    </h3>
                    {a[cell.key].length ? (
                      <ul>
                        {a[cell.key].map((reply) => (
                          <li key={reply.message_id}>
                            <Link href={replyHref(reply)}>{replyName(reply)}</Link>
                          </li>
                        ))}
                      </ul>
                    ) : null}
                  </section>
                ))}
              </Card>
            </div>
          ))
        : null}
      <Card title="Reader">
        <div className="ag-table-wrap"><table className="ag-table">
          <thead>
            <tr>
              <th scope="col">Signal</th>
              <th scope="col">Kind</th>
              <th scope="col">Tracks</th>
              <th scope="col">Present at</th>
            </tr>
          </thead>
          <tbody>
            {data.reader.signals.map((s) => (
              <tr key={s.name}>
                <th scope="row" title={s.description}>
                  {labelName(s.name)}
                  <div className="ag-quiet">{s.description}</div>
                </th>
                <td>{SIGNAL_KINDS[s.kind] ?? s.kind}</td>
                <td>{s.label ? labelName(s.label) : "No label"}</td>
                <td>{s.present_at ?? "Not set"}</td>
              </tr>
            ))}
          </tbody>
        </table></div>
      </Card>
      <Card title="Run">
        <Provenance run={data.run} />
      </Card>
    </>
  );
}
