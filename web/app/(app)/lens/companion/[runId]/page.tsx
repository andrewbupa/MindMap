import { Notice, PageHeader } from "@/components/ui";
import { readCompanionRun } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { CompanionRunView } from "./CompanionRunView";

export const metadata = { title: "Companion run" };

export default async function CompanionRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ lens_run?: string }>;
}) {
  const [{ runId }, { lens_run }] = await Promise.all([params, searchParams]);
  const { data } = await readCompanionRun({
    client: await serverClient(),
    path: { run_id: runId },
    query: { lens_run },
  });
  if (!data) {
    return (
      <>
        <PageHeader title="Companion run" />
        <Notice>This companion run could not be opened.</Notice>
      </>
    );
  }
  return <CompanionRunView data={data} />;
}
