import Link from "next/link";

import { Notice, PageHeader } from "@/components/ui";
import { listAgents, readBehaviour } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { SuiteForm } from "./SuiteForm";

export const metadata = { title: "Start a suite" };

export default async function NewSuitePage({
  searchParams,
}: {
  searchParams: Promise<{ behaviour?: string; set?: string }>;
}) {
  const { behaviour: key, set } = await searchParams;
  if (!key) {
    return (
      <>
        <PageHeader title="Start a suite" />
        <Notice>
          Start a suite from a behaviour&apos;s page in <Link href="/tally">Tally</Link>.
        </Notice>
      </>
    );
  }
  const client = await serverClient();
  const [{ data: behaviour }, { data: agents }] = await Promise.all([
    readBehaviour({ client, path: { key }, query: { scenario_set: set }, throwOnError: true }),
    listAgents({ client, throwOnError: true }),
  ]);
  const scenarioSet = behaviour.scenario_sets.find((item) => item.id === behaviour.selected_set);
  return (
    <>
      <PageHeader title={`Start a suite: ${behaviour.title}`}>
        <p>
          Every prompt version you choose faces the same scenarios, each repeated so the spread
          shows. Each scenario, at each repetition, runs as its own job.
        </p>
      </PageHeader>
      {scenarioSet ? (
        <SuiteForm
          behaviour={behaviour.key}
          scenarioSet={scenarioSet}
          agents={agents.filter((a) => !behaviour.agents.length || behaviour.agents.includes(a.key))}
        />
      ) : (
        <Notice>
          This behaviour has no scenarios yet. Generate them on{" "}
          <Link href={`/tally/behaviours/${behaviour.key}`}>its page</Link> first.
        </Notice>
      )}
    </>
  );
}
