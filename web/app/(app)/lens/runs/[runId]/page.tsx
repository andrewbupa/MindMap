import { listLensRuns, readLensRun } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

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
  const [{ data: run }, { data: others }] = await Promise.all([
    readLensRun({ client, path: { run_id: runId }, query: { label }, throwOnError: true }),
    listLensRuns({ client, throwOnError: true }),
  ]);
  return (
    <LensRunView
      run={run}
      label={label ?? null}
      others={others.filter((o) => o.run.id !== runId && o.run.status === "succeeded")}
    />
  );
}
