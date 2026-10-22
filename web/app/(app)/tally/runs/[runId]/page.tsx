import { readTallyRun } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { TallyRunView } from "./TallyRunView";

export const metadata = { title: "Tally run" };

export default async function TallyRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const { data: run } = await readTallyRun({
    client: await serverClient(),
    path: { run_id: runId },
    throwOnError: true,
  });
  return <TallyRunView run={run} />;
}
