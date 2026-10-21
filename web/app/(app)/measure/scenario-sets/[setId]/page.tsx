import Link from "next/link";

import styles from "@/components/measure/measure.module.css";
import { Provenance } from "@/components/runs/Provenance";
import { Badge, Card, Mono, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { readScenarioSet } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Scenario set" };

export default async function ScenarioSetPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = await params;
  const { data: set } = await readScenarioSet({
    client: await serverClient(),
    path: { scenario_set_id: setId },
    throwOnError: true,
  });
  const title = sentenceCase(set.behaviour.replaceAll("_", " "));
  return (
    <>
      <PageHeader title={`Scenarios: ${title}`}>
        <p>
          Bloom wrote these from{" "}
          <Link href={`/measure/behaviours/${set.behaviour}?set=${set.summary.id}`}>
            the behaviour&apos;s definition
          </Link>{" "}
          on {formatWhen(set.summary.created_at)}
          {set.summary.current ? "" : ", from an earlier version of it"}. They never change; a
          new set is a new generation.
        </p>
      </PageHeader>
      <Card title="Scenarios">
        <table>
          <thead>
            <tr>
              <th scope="col">Scenario</th>
              <th scope="col">Variation</th>
            </tr>
          </thead>
          <tbody>
            {set.scenarios.map((scenario) => (
              <tr key={scenario.id} id={`scenario-${scenario.id}`}>
                <td>
                  <details>
                    <summary>{sentenceCase(scenario.id.replaceAll("_", " "))}</summary>
                    <p className={styles.seed}>{scenario.seed}</p>
                  </details>
                </td>
                <td>
                  {scenario.variation ? (
                    <Badge>{sentenceCase(scenario.variation.replaceAll("_", " "))}</Badge>
                  ) : (
                    "Base scenario"
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Judge dimensions">
        {set.dimensions.map((dimension) => (
          <details key={dimension.name} open={dimension.presence}>
            <summary>
              <Mono>{dimension.name}</Mono> {dimension.presence ? <Badge>Presence</Badge> : null}
            </summary>
            <p>{dimension.description}</p>
            {dimension.rubric ? <p className={styles.seed}>{dimension.rubric}</p> : null}
          </details>
        ))}
      </Card>
      <Card title="Bloom's understanding">
        {set.understanding ? <p className={styles.seed}>{set.understanding}</p> : null}
        {set.scientific_motivation ? (
          <details>
            <summary>Why it is worth measuring</summary>
            <p className={styles.seed}>{set.scientific_motivation}</p>
          </details>
        ) : null}
      </Card>
      <Card title="Generation">
        <table>
          <tbody>
            <tr>
              <th scope="row">Content hash</th>
              <td>
                <Mono>{set.summary.content_hash.slice(0, 16)}</Mono>
              </td>
            </tr>
            <tr>
              <th scope="row">Behaviour seed hash</th>
              <td>
                <Mono>{set.summary.behaviour_seed_hash.slice(0, 16)}</Mono>
              </td>
            </tr>
          </tbody>
        </table>
        <Provenance run={set.generation} />
      </Card>
    </>
  );
}
