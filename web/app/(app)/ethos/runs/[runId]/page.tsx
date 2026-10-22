import { listWitnessRuns, listEthosRuns, listReaders, readEthosRun } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { EthosRunView } from "./EthosRunView";

export const metadata = { title: "Ethos run" };

export default async function EthosRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ label?: string }>;
}) {
  const [{ runId }, { label }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const [{ data: run }, { data: others }, { data: readers }, user] = await Promise.all([
    readEthosRun({ client, path: { run_id: runId }, query: { label }, throwOnError: true }),
    listEthosRuns({ client, throwOnError: true }),
    listReaders({ client, throwOnError: true }),
    getMe(),
  ]);
  const { data: companions } = await listWitnessRuns({
    client,
    query: { source_run: run.source.id },
    throwOnError: true,
  });
  return (
    <EthosRunView
      run={run}
      label={label ?? null}
      others={others.filter((o) => o.run.id !== runId && o.run.status === "succeeded")}
      witness={{ runs: companions, readers, canLaunch: user !== null && hasRole(user, "author") }}
    />
  );
}
