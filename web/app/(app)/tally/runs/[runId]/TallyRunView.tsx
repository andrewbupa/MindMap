"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useEffect, useRef } from "react";

import { meanText, percent, spreadText, tallyText } from "@/components/tally/format";
import styles from "@/components/tally/tally.module.css";
import { Provenance } from "@/components/runs/Provenance";
import runStyles from "@/components/runs/runs.module.css";
import { Badge, Card, Mono, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readTallyRun, type TallyRunOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

type Live = { status: string; tokens_used: number; counts: Record<string, number> };

const OPEN = new Set(["queued", "running"]);

function label(value: string): string {
  return sentenceCase(value.replaceAll("_", " "));
}

export function TallyRunView({ run }: { run: TallyRunOut }) {
  const router = useRouter();
  // The counts below link here with a filter, so each number opens the rollouts behind it.
  const params = useSearchParams();
  const repetition = params.get("repetition");
  const only = params.get("scenario");
  const rollouts = run.rollouts.filter(
    (r) => (!repetition || String(r.epoch) === repetition) && (!only || r.scenario === only),
  );
  const initial: Live = { status: run.run.status, tokens_used: run.run.tokens_used, counts: run.counts };
  const live = useLiveStatus<Live>({
    streamUrl: `/api/tally/runs/${run.run.id}/events`,
    poll: async () => {
      const { data } = await readTallyRun({ client: browserClient, path: { run_id: run.run.id } });
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
  const { elicitation } = run;
  const threshold = elicitation.threshold;
  return (
    <>
      <PageHeader title={run.run.title}>
        <p>
          <Link href={`/agents/${run.agent}/versions/${run.version}`}>
            {run.agent} {run.version}
          </Link>{" "}
          on{" "}
          <Link href={`/tally/behaviours/${run.behaviour}?set=${run.scenario_set}`}>
            {label(run.behaviour)}
          </Link>
          , using <Link href={`/tally/scenario-sets/${run.scenario_set}`}>its scenario set</Link>.
        </p>
      </PageHeader>
      <Card title="Progress">
        <div className={runStyles.counts}>
          {Object.entries(counts).map(([status, n]) => (
            <Badge key={status}>
              {sentenceCase(status)}: {n}
            </Badge>
          ))}
          <span className={runStyles.quiet}>{total} rollouts in all.</span>
        </div>
        {run.run.error ? <Notice tone="danger">{run.run.error}</Notice> : null}
        {OPEN.has(live?.status ?? run.run.status) ? null : (
          <p>
            <Link href={`/ethos?source=${run.run.id}`}>Read these conversations with Ethos</Link>
          </p>
        )}
      </Card>
      <Card title="Elicitation rate">
        <div className={styles.stats}>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Rate</span>
            <a className={styles.statValue} href="#rollouts">
              {percent(elicitation.overall.rate)}
            </a>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Scored {threshold} or more</span>
            <a className={styles.statValue} href="#rollouts">
              {tallyText(elicitation.overall)}
            </a>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Across repetitions</span>
            <a className={styles.statValue} href="#repetitions">
              {spreadText(elicitation)}
            </a>
          </div>
          <div className={styles.stat}>
            <span className={styles.statLabel}>Mean presence</span>
            <span className={styles.statValue}>{meanText(elicitation.overall)}</span>
          </div>
        </div>
        <p className={styles.quiet}>
          Cite this rate with its seed hash, <Mono>{run.run.seed_hash?.slice(0, 16)}</Mono>.
          {elicitation.overall.unscored
            ? ` ${elicitation.overall.unscored} rollouts the judge did not score are left out.`
            : ""}
        </p>
        <h3 id="repetitions">Each repetition</h3>
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Repetition</th>
              <th scope="col">Rate</th>
              <th scope="col">Scored {threshold} or more</th>
              <th scope="col">Mean presence</th>
            </tr>
          </thead>
          <tbody>
            {elicitation.by_epoch.map((epoch) => (
              <tr key={epoch.epoch}>
                <td>{epoch.epoch}</td>
                <td>{percent(epoch.rate)}</td>
                <td>
                  <Link href={`?repetition=${epoch.epoch}#rollouts`}>{tallyText(epoch)}</Link>
                </td>
                <td>{meanText(epoch)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="By scenario">
        <table className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">Variation</th>
              <th scope="col">Scored {threshold} or more</th>
              <th scope="col">Mean presence</th>
            </tr>
          </thead>
          <tbody>
            {run.by_scenario.map((scenario) => (
              <tr key={scenario.scenario}>
                <td>
                  <Link href={`/tally/scenario-sets/${run.scenario_set}#scenario-${scenario.scenario}`}>
                    {label(scenario.scenario)}
                  </Link>
                </td>
                <td>{scenario.variation ? label(scenario.variation) : "Base"}</td>
                <td>
                  <Link href={`?scenario=${scenario.scenario}#rollouts`}>{tallyText(scenario)}</Link>
                </td>
                <td>{meanText(scenario)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Rollouts, highest presence first">
        {repetition || only ? (
          <p>
            Showing {only ? label(only) : "every scenario"}
            {repetition ? `, repetition ${repetition}` : ""}.{" "}
            <Link href="?#rollouts">Show every rollout</Link>
          </p>
        ) : null}
        <table id="rollouts" className={styles.numbers}>
          <thead>
            <tr>
              <th scope="col">Presence</th>
              <th scope="col">Scenario</th>
              <th scope="col">Repetition</th>
              <th scope="col">Judge&apos;s summary</th>
            </tr>
          </thead>
          <tbody>
            {rollouts.map((rollout) => (
              <tr key={rollout.transcript_id}>
                <td>
                  <Link href={`/tally/transcripts/${rollout.transcript_id}`}>
                    {rollout.score === null || rollout.score === undefined ? (
                      <Badge>Not scored</Badge>
                    ) : (
                      <Badge tone={rollout.score >= threshold ? "danger" : "neutral"}>
                        {rollout.score} of 10
                      </Badge>
                    )}
                  </Link>
                </td>
                <td>
                  {label(rollout.scenario)}
                  {rollout.content_notes.map((note) => (
                    <Badge key={note} tone="warn">
                      Content note: {sentenceCase(note)}
                    </Badge>
                  ))}
                </td>
                <td>{rollout.epoch}</td>
                <td className={styles.quiet}>{rollout.summary}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Run">
        <Provenance run={run.run} />
      </Card>
    </>
  );
}
