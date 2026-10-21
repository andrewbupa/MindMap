import Link from "next/link";

import { percent } from "@/components/measure/format";
import { latestByVersion } from "@/components/measure/RateTable";
import { StatusBadge } from "@/components/runs/Provenance";
import { Badge, Card, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { listBehaviours, listMeasureRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Measure" };

export default async function MeasurePage() {
  const client = await serverClient();
  const [{ data: behaviours }, { data: runs }] = await Promise.all([
    listBehaviours({ client, throwOnError: true }),
    listMeasureRuns({ client, throwOnError: true }),
  ]);
  return (
    <>
      <PageHeader title="Measure">
        <p>
          Bloom turns one behaviour into a rate: the share of conversations a judge scores 7 or
          more out of 10 for it. Each prompt version faces the same generated scenarios, three
          times over, so rates can be compared.
        </p>
      </PageHeader>
      <Card title="Behaviours">
        <table>
          <thead>
            <tr>
              <th scope="col">Behaviour</th>
              <th scope="col">Agents</th>
              <th scope="col">Scenarios</th>
              <th scope="col">Latest rates</th>
            </tr>
          </thead>
          <tbody>
            {behaviours.map((behaviour) => {
              const latest = latestByVersion(runs.filter((run) => run.behaviour === behaviour.key));
              return (
                <tr key={behaviour.key}>
                  <td>
                    <Link href={`/measure/behaviours/${behaviour.key}`}>{behaviour.title}</Link>
                    {behaviour.content_notes.map((note) => (
                      <Badge key={note} tone="warn">
                        Content note: {sentenceCase(note)}
                      </Badge>
                    ))}
                  </td>
                  <td>{behaviour.agents.join(", ") || "Any"}</td>
                  <td>
                    {behaviour.generating ? (
                      <StatusBadge status={behaviour.generating.status} />
                    ) : behaviour.scenario_set ? (
                      <Link href={`/measure/scenario-sets/${behaviour.scenario_set.id}`}>
                        {behaviour.scenario_set.scenario_count} scenarios
                      </Link>
                    ) : (
                      "Not generated yet"
                    )}
                  </td>
                  <td>
                    {latest.length === 0
                      ? "No suites yet"
                      : latest.map((run, index) => (
                          <span key={run.run.id}>
                            {index ? ", " : ""}
                            {run.version}:{" "}
                            <Link href={`/measure/runs/${run.run.id}`}>
                              {percent(run.elicitation.overall.rate)}
                            </Link>
                          </span>
                        ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
      <Card title="Recent suites">
        {runs.length === 0 ? (
          <p>No suites yet. Generate a behaviour&apos;s scenarios, then start a suite from its page.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Status</th>
                <th scope="col">Rate</th>
                <th scope="col">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.slice(0, 20).map((run) => (
                <tr key={run.run.id}>
                  <td>
                    <Link href={`/measure/runs/${run.run.id}`}>{run.run.title}</Link>
                  </td>
                  <td>
                    <StatusBadge status={run.run.status} />
                  </td>
                  <td>
                    <Link href={`/measure/runs/${run.run.id}#rollouts`}>
                      {percent(run.elicitation.overall.rate)}
                    </Link>
                  </td>
                  <td>{formatWhen(run.run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
