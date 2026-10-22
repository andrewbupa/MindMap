import Link from "next/link";

import { GenerationPanel } from "@/components/tally/GenerationPanel";
import { RateChart } from "@/components/tally/RateChart";
import { RateTable, latestByVersion } from "@/components/tally/RateTable";
import styles from "@/components/tally/tally.module.css";
import { StatusBadge } from "@/components/runs/Provenance";
import { Badge, Card, Mono, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { readBehaviour } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Behaviour" };

export default async function BehaviourPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ set?: string }>;
}) {
  const [{ key }, { set }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const [user, { data: behaviour }] = await Promise.all([
    getMe(),
    readBehaviour({ client, path: { key }, query: { scenario_set: set }, throwOnError: true }),
  ]);
  const author = user !== null && hasRole(user, "author");
  const selected = behaviour.scenario_sets.find((item) => item.id === behaviour.selected_set);
  const latest = latestByVersion(behaviour.runs);
  const earlier = behaviour.runs.filter((run) => !latest.includes(run));

  return (
    <>
      <PageHeader title={behaviour.title}>
        <p>{behaviour.definition.split("\n\n")[0]}</p>
      </PageHeader>

      <Card title="Elicitation rate by prompt version">
        {selected ? (
          <p className={styles.quiet}>
            On scenario set{" "}
            <Link href={`/tally/scenario-sets/${selected.id}`}>
              <Mono>{selected.content_hash.slice(0, 12)}</Mono>
            </Link>{" "}
            ({selected.scenario_count} scenarios, generated {formatWhen(selected.created_at)}).
            Rates are comparable only within one scenario set.
          </p>
        ) : null}
        {latest.length ? (
          <>
            <RateChart
              points={latest.map((run) => ({
                label: run.version,
                href: `/tally/runs/${run.run.id}`,
                elicitation: run.elicitation,
              }))}
            />
            <RateTable runs={latest} />
          </>
        ) : (
          <p>No finished suites on this scenario set yet.</p>
        )}
        {author && selected ? (
          <p>
            <Link href={`/tally/new?behaviour=${behaviour.key}&set=${selected.id}`}>
              Start a suite on this scenario set
            </Link>
          </p>
        ) : null}
        {earlier.length ? (
          <details>
            <summary>Earlier and unfinished runs ({earlier.length})</summary>
            <RateTable runs={earlier} />
          </details>
        ) : null}
      </Card>

      <Card title="Highest presence scores">
        {behaviour.top_rollouts.length === 0 ? (
          <p>No scored rollouts yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Presence</th>
                <th scope="col">Scenario</th>
                <th scope="col">Prompt version</th>
                <th scope="col">Repetition</th>
                <th scope="col">Judge&apos;s summary</th>
              </tr>
            </thead>
            <tbody>
              {behaviour.top_rollouts.map((rollout) => (
                <tr key={rollout.transcript_id}>
                  <td>
                    <Link href={`/tally/transcripts/${rollout.transcript_id}`}>
                      <Badge tone={(rollout.score ?? 0) >= 7 ? "danger" : "neutral"}>
                        {rollout.score} of 10
                      </Badge>
                    </Link>
                  </td>
                  <td>
                    {sentenceCase(rollout.scenario.replaceAll("_", " "))}
                    {rollout.variation ? (
                      <Badge>{sentenceCase(rollout.variation.replaceAll("_", " "))}</Badge>
                    ) : null}
                    {rollout.content_notes.map((note) => (
                      <Badge key={note} tone="warn">
                        Content note: {sentenceCase(note)}
                      </Badge>
                    ))}
                  </td>
                  <td>{rollout.version}</td>
                  <td>{rollout.epoch}</td>
                  <td className={styles.quiet}>{rollout.summary}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>

      <Card title="Scenarios">
        {behaviour.scenario_set ? (
          <p>
            The current scenario set has{" "}
            <Link href={`/tally/scenario-sets/${behaviour.scenario_set.id}`}>
              {behaviour.scenario_set.scenario_count} scenarios
            </Link>
: base scenarios Bloom wrote from the definition, and a variation of each for{" "}
            {behaviour.variations.map((v) => v.replaceAll("_", " ")).join(" and ")}. The judge
            scores presence on <Mono>{behaviour.scenario_set.presence_dimension}</Mono>.
          </p>
        ) : (
          <p>
            This version of the behaviour has no scenarios yet. Generation runs Bloom&apos;s
            understanding and ideation once; every suite then reuses the result.
          </p>
        )}
        <GenerationPanel
          behaviour={behaviour.key}
          generating={behaviour.generating}
          canGenerate={author}
          hasCurrent={behaviour.scenario_set !== null}
        />
        {behaviour.scenario_sets.length > 1 ? (
          <>
            <h3>Every scenario set</h3>
            <table>
              <thead>
                <tr>
                  <th scope="col">Set</th>
                  <th scope="col">Scenarios</th>
                  <th scope="col">Behaviour version</th>
                  <th scope="col">Generated</th>
                </tr>
              </thead>
              <tbody>
                {behaviour.scenario_sets.map((item) => (
                  <tr key={item.id}>
                    <td>
                      <Link href={`/tally/behaviours/${behaviour.key}?set=${item.id}`}>
                        <Mono>{item.content_hash.slice(0, 12)}</Mono>
                      </Link>
                      {item.id === behaviour.selected_set ? <Badge>Shown</Badge> : null}
                    </td>
                    <td>
                      <Link href={`/tally/scenario-sets/${item.id}`}>{item.scenario_count}</Link>
                    </td>
                    <td>{item.current ? "Current" : "Earlier"}</td>
                    <td>{formatWhen(item.created_at)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </>
        ) : null}
        {behaviour.generations.length ? (
          <details>
            <summary>Generation runs ({behaviour.generations.length})</summary>
            <table>
              <tbody>
                {behaviour.generations.map((run) => (
                  <tr key={run.id}>
                    <td>{formatWhen(run.created_at)}</td>
                    <td>
                      <StatusBadge status={run.status} />
                    </td>
                    <td>{run.tokens_used.toLocaleString("en-AU")} tokens</td>
                    <td className={styles.quiet}>{run.error}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </details>
        ) : null}
      </Card>

      <Card title="Behaviour version">
        <table>
          <tbody>
            <tr>
              <th scope="row">Seed hash</th>
              <td>
                <Mono>{behaviour.seed_hash.slice(0, 16)}</Mono>
                <br />
                <span className={styles.quiet}>
                  Over seeds/bloom/{behaviour.key}. Cite every rate with its run&apos;s seed hash.
                </span>
              </td>
            </tr>
            <tr>
              <th scope="row">Agents</th>
              <td>{behaviour.agents.join(", ") || "Any"}</td>
            </tr>
            <tr>
              <th scope="row">Variations</th>
              <td>{behaviour.variations.map((v) => sentenceCase(v.replaceAll("_", " "))).join(", ")}</td>
            </tr>
            <tr>
              <th scope="row">Ethos scenario type</th>
              <td>{behaviour.scenario_type ? sentenceCase(behaviour.scenario_type.replaceAll("_", " ")) : "None"}</td>
            </tr>
          </tbody>
        </table>
        <details>
          <summary>The full definition</summary>
          <p className={styles.seed}>{behaviour.definition}</p>
        </details>
      </Card>
    </>
  );
}
