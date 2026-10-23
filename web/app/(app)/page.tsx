import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { RunTable } from "@/components/runs/RunTable";
import { KIND_NAMES, runHref } from "@/components/runs/href";
import { percent } from "@/components/tally/format";
import {
  Badge,
  ButtonLink,
  Card,
  Mono,
  Notice,
  PageHeader,
  formatUsd,
  formatWhen,
  sentenceCase,
} from "@/components/ui";
import { spend, weekInReview, type WeekOut } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

function Regressions({ week }: { week: WeekOut }) {
  const rows: Row[] = week.regressions.map((r) => {
    const points = Math.round((r.rate - r.previous_rate) * 100);
    return {
      id: r.run_id,
      cells: {
        behaviour: <Link href={`/tally/behaviours/${r.behaviour}?set=${r.scenario_set}`}>{r.behaviour_title}</Link>,
        agent: <Mono plain>{r.agent}</Mono>,
        before: (
          <span className="ag-num">
            {r.previous_version} <Link href={`/tally/runs/${r.previous_run_id}`}>{percent(r.previous_rate)}</Link>
          </span>
        ),
        after: (
          <span className="ag-num">
            {r.version} <Link href={`/tally/runs/${r.run_id}`}>{percent(r.rate)}</Link>
          </span>
        ),
        change: <Badge tone="danger">Worse by {points} points</Badge>,
      },
      sort: { behaviour: r.behaviour_title, agent: r.agent, change: points },
    };
  });
  return (
    <Card title="Regressions by prompt version" id="regressions">
      <p className="ag-quiet">
        A prompt version whose Tally elicitation rate rose over the version before it, on the same behaviour and
        scenario set, where the newer run finished this week. A higher rate of the behaviour is worse.
      </p>
      <DataTable
        columns={[
          { key: "behaviour", label: "Behaviour" },
          { key: "agent", label: "Agent" },
          { key: "before", label: "Before", align: "right", sortable: false },
          { key: "after", label: "After", align: "right", sortable: false },
          { key: "change", label: "Change", nowrap: true },
        ]}
        rows={rows}
        initialSort={{ key: "change", dir: "desc" }}
        empty="No prompt version’s rate rose this week."
      />
    </Card>
  );
}

function Awaiting({ week }: { week: WeekOut }) {
  const awaiting = week.awaiting;
  if (!awaiting) return null;
  const count = (n: number) => (awaiting.capped && n >= 50 ? "50 or more" : String(n));
  const queues = [
    { href: "/jury", label: "Judge scores", n: awaiting.scores },
    { href: "/jury/ethos", label: "Ethos disagreements", n: awaiting.ethos },
    { href: "/jury/gold", label: "Gold-set transcripts to label", n: awaiting.gold },
  ];
  return (
    <Card title="Waiting for you in Jury">
      <dl className="ag-stats" style={{ marginBottom: 0 }}>
        {queues.map((queue) => (
          <div key={queue.href} className="ag-stat">
            <dt>{queue.label}</dt>
            <dd>
              <Link href={queue.href}>{count(queue.n)}</Link>
            </dd>
          </div>
        ))}
      </dl>
      {awaiting.hidden_for_content_notes > 0 ? (
        <p className="ag-quiet" style={{ marginBottom: 0 }}>
          {awaiting.hidden_for_content_notes} more touch self-harm, abuse or bereavement and are hidden. You can opt in
          under <Link href="/settings/preferences">your preferences</Link>.
        </p>
      ) : null}
    </Card>
  );
}

export default async function HomePage() {
  const user = await getMe();
  if (!user) return null;
  if (user.roles.length === 0) {
    return (
      <>
        <PageHeader title={`Welcome, ${user.name}`} />
        <Notice>
          You are signed in, but you have no role yet. An admin will grant you access as an author, reviewer or
          compliance reader.
        </Notice>
      </>
    );
  }
  const client = await serverClient();
  const [{ data: week }, { data: money }] = await Promise.all([
    weekInReview({ client, throwOnError: true }),
    spend({ client, query: { months: 1 }, throwOnError: true }),
  ]);
  const thisMonth = money.months[0];
  const kinds = Object.entries(week.by_kind).sort(([, a], [, b]) => b - a);
  const started = kinds.reduce((sum, [, n]) => sum + n, 0);
  return (
    <>
      <PageHeader
        title={`Welcome, ${user.name}`}
        intro={`The week in review, since ${formatWhen(week.since)}.`}
        actions={hasRole(user, "author") ? <ButtonLink href="/inquiry/new">Start an audit</ButtonLink> : null}
      />

      <Card title="This week">
        <dl className="ag-stats">
          <div className="ag-stat">
            <dt>Runs started</dt>
            <dd>
              <Link href="/record">{started}</Link>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Finished</dt>
            <dd>
              <Link href="/record">{week.finished}</Link>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Failed</dt>
            <dd>
              <Link href="/record">{week.failed}</Link>
            </dd>
          </div>
          <div className="ag-stat">
            <dt>Regressions</dt>
            <dd>
              <a href="#regressions">{week.regressions.length}</a>
            </dd>
          </div>
          {thisMonth ? (
            <div className="ag-stat">
              <dt>Estimated spend this month</dt>
              <dd>
                <Link href="/settings/spend">{formatUsd(thisMonth.cost_usd)}</Link>
              </dd>
            </div>
          ) : null}
        </dl>
        {kinds.length ? (
          <p className="ag-row" style={{ gap: "var(--space-2)", marginBottom: 0 }}>
            {kinds.map(([kind, n]) => (
              <Link key={kind} href={`/record?kind=${kind}`} className="ag-badge">
                {KIND_NAMES[kind] ?? sentenceCase(kind)}: {n}
              </Link>
            ))}
          </p>
        ) : (
          <p className="ag-quiet" style={{ marginBottom: 0 }}>
            No runs started this week.
          </p>
        )}
      </Card>

      <Regressions week={week} />
      <Awaiting week={week} />

      <Card title="New runs" actions={<Link href="/record">Every run, in Record</Link>}>
        <RunTable
          runs={week.runs}
          href={(run) => runHref(run) ?? "/record"}
          extra={[
            {
              column: { key: "kind", label: "Kind" },
              cell: (run) => KIND_NAMES[run.kind] ?? run.kind,
              sort: (run) => run.kind,
            },
          ]}
          empty="No runs started this week."
        />
      </Card>

      <Card title="Three ways to test an agent">
        <ul style={{ margin: 0, paddingLeft: "var(--space-5)", display: "grid", gap: "var(--space-2)" }}>
          <li>
            <Link href="/inquiry">Inquiry</Link> asks what could go wrong across many situations.
          </li>
          <li>
            <Link href="/tally">Tally</Link> asks how often one chosen behaviour occurs.
          </li>
          <li>
            <Link href="/ethos">Ethos</Link> asks which dispositions an agent expressed, how strongly, and whether
            they suited the moment.
          </li>
        </ul>
      </Card>
    </>
  );
}
