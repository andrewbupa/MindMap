import { readInquiryRun, listDimensions } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { RunView } from "./RunView";

export const metadata = { title: "Audit" };

export default async function AuditPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const client = await serverClient();
  const [{ data: run }, { data: dimensions }] = await Promise.all([
    readInquiryRun({ client, path: { run_id: runId }, throwOnError: true }),
    listDimensions({ client, throwOnError: true }),
  ]);
  return <RunView run={run} dimensions={dimensions} />;
}
