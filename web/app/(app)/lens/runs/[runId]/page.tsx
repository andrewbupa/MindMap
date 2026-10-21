import { listCompanionRuns, listLensRuns, listReaders, readLensRun } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { LensRunView } from "./LensRunView";

export const metadata = { title: "Lens run" };

export default async function LensRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ label?: string }>;
}) {
  const [{ runId }, { label }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const [{ data: run }, { data: others }, { data: readers }, user] = await Promise.all([
    readLensRun({ client, path: { run_id: runId }, query: { label }, throwOnError: true }),
    listLensRuns({ client, throwOnError: true }),
    listReaders({ client, throwOnError: true }),
    getMe(),
  ]);
  const { data: companions } = await listCompanionRuns({
    client,
    query: { source_run: run.source.id },
    throwOnError: true,
  });
  return (
    <LensRunView
      run={run}
      label={label ?? null}
      others={others.filter((o) => o.run.id !== runId && o.run.status === "succeeded")}
      companion={{ runs: companions, readers, canLaunch: user !== null && hasRole(user, "author") }}
    />
  );
}
