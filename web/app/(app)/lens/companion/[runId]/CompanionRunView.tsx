"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef } from "react";

import { SIGNAL_KINDS, familyColour, labelName } from "@/components/lens/family";
import styles from "@/components/lens/lens.module.css";
import { Provenance } from "@/components/runs/Provenance";
import runStyles from "@/components/runs/runs.module.css";
import { Badge, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readCompanionRun, type CompanionRunOut, type ReplyRefOut, type SignalAgreementOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };
type Cell = "both" | "lens_only" | "companion_only" | "neither";

const OPEN = new Set(["queued", "running"]);
const CELLS: { key: Cell; name: string }[] = [
  { key: "both", name: "Both" },
  { key: "lens_only", name: "Lens only" },
  { key: "companion_only", name: "Signal only" },
  { key: "neither", name: "Neither" },
];
const QUIET =
  "Signals from an open-weight model reading the text. They show how that model represents the conversation, not the agent's own internals.";

function percent(value: number | null | undefined): string {
  return value === null || value === undefined ? "None to compare" : `${Math.round(value * 100)}%`;
}

export function CompanionRunView({ data }: { data: CompanionRunOut }) {
  const router = useRouter();
  const initial: Live = { status: data.run.status, tokens_used: data.run.tokens_used, counts: data.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/companion/runs/${data.run.id}/events`,
    poll: async () => {
      const { data: next } = await readCompanionRun({ client: browserClient, path: { run_id: data.run.id } });
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
  const lens = data.lens_run;
  const transcripts = (data.run.config.transcripts as string[]).length;

  function replyHref(reply: ReplyRefOut): string {
    return `/lens/runs/${lens?.id}/transcripts/${reply.transcript_id}?companion=${data.run.id}#r-${reply.message_id}`;
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
      <PageHeader title={data.run.title} quiet={QUIET}>
        <p>
          {data.reader.model} read {transcripts} conversations from{" "}
          {lens ? <Link href={`/lens/runs/${lens.id}`}>{data.source.title}</Link> : data.source.title} with
          the reader {data.reader.key}, version {data.reader.version}.
        </p>
      </PageHeader>
      <Card title="Progress">
        <div className={runStyles.counts}>
          {Object.entries(counts).map(([status, n]) => (
            <Badge key={status}>
              {sentenceCase(status)}: {n}
            </Badge>
          ))}
        </div>
        {waiting ? (
          <p className={styles.quiet}>
            Companion jobs wait on the companion queue until the Droplet runner takes them. If they stay
            queued, check the runner (see the runbook).
          </p>
        ) : null}
        {data.run.error ? <Notice tone="danger">{data.run.error}</Notice> : null}
        {Object.keys(data.dropped).length ? (
          <p className={styles.quiet}>
            Signals dropped by the checks:{" "}
            {Object.entries(data.dropped)
              .map(([reason, n]) => `${n} (${reason.replaceAll("_", " ")})`)
              .join("; ")}
            . They count nowhere.
          </p>
        ) : null}
      </Card>
      <Card title="Signals beside Lens labels">
        {!lens ? (
          <p>
            No finished Lens run reads {data.source.title}, so there is nothing to compare yet.{" "}
            <Link href={`/lens?source=${data.source.id}`}>Read it with Lens</Link>.
          </p>
        ) : (
          <>
            <p className={styles.quiet}>
              Compared with <Link href={`/lens/runs/${lens.id}`}>{lens.title}</Link>, over the replies both
              read. Lens counts a label when the panel&apos;s median intensity is 1 or more; a signal counts
              when any token reaches its threshold. Each count opens its replies.
            </p>
            {data.lens_runs.length > 1 ? (
              <p>
                Other Lens runs on this source:{" "}
                {data.lens_runs
                  .filter((r) => r.id !== lens.id)
                  .map((r, i) => (
                    <span key={r.id}>
                      {i ? ", " : ""}
                      <Link href={`/lens/companion/${data.run.id}?lens_run=${r.id}`}>{r.title}</Link>
                    </span>
                  ))}
              </p>
            ) : null}
            {data.agreements.length === 0 ? (
              <p>None of this reader&apos;s signals is tied to a Lens label.</p>
            ) : (
              <table className={styles.numbers}>
                <thead>
                  <tr>
                    <th scope="col">Signal</th>
                    <th scope="col">Lens label</th>
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
                        <div className={styles.quiet}>{SIGNAL_KINDS[a.kind] ?? a.kind}</div>
                      </th>
                      <td>
                        <span className={styles.swatch} style={{ background: familyColour(a.family) }} />
                        <Link href={`/lens/runs/${lens.id}?label=${a.label}`}>{labelName(a.label)}</Link>
                        {a.trust_status ? (
                          <>
                            {" "}
                            <Badge tone={a.trust_status === "trusted" ? "ok" : "neutral"}>
                              {sentenceCase(a.trust_status)}
                            </Badge>
                          </>
                        ) : null}
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
              </table>
            )}
          </>
        )}
      </Card>
      {lens
        ? data.agreements.map((a) => (
            <div key={a.signal} id={`signal-${a.signal}`}>
              <Card title={`${labelName(a.signal)} beside ${labelName(a.label).toLowerCase()}`}>
                <p className={styles.quiet}>
                  {a.replies} replies. They agree on {a.both.length + a.neither.length} ({percent(a.agreement)}).
                  Of the {a.both.length + a.lens_only.length + a.companion_only.length} that either flags,
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
        <table>
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
                  <div className={styles.quiet}>{s.description}</div>
                </th>
                <td>{SIGNAL_KINDS[s.kind] ?? s.kind}</td>
                <td>{s.label ? labelName(s.label) : "No label"}</td>
                <td>{s.present_at ?? "Not set"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Run">
        <Provenance run={data.run} />
      </Card>
    </>
  );
}
