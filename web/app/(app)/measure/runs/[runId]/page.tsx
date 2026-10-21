import { readMeasureRun } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { MeasureRunView } from "./MeasureRunView";

export const metadata = { title: "Measure run" };

export default async function MeasureRunPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const { data: run } = await readMeasureRun({
    client: await serverClient(),
    path: { run_id: runId },
    throwOnError: true,
  });
  return <MeasureRunView run={run} />;
}
