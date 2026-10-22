import { PageHeader } from "@/components/ui";
import { listAgents } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { LaunchForm } from "./LaunchForm";

export const metadata = { title: "Start an audit" };

export default async function NewAuditPage() {
  const { data: agents } = await listAgents({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader
        title="Start an audit"
        intro="Choose an agent version and the seeds to audit it with. Each seed, at each repetition, runs as its own job."
      />
      <LaunchForm agents={agents} />
    </>
  );
}
