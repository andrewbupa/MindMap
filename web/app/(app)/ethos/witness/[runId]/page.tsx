import { Notice, PageHeader } from "@/components/ui";
import { readWitnessRun } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { WitnessRunView } from "./WitnessRunView";

export const metadata = { title: "Witness run" };

export default async function WitnessRunPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string }>;
  searchParams: Promise<{ ethos_run?: string }>;
}) {
  const [{ runId }, { ethos_run }] = await Promise.all([params, searchParams]);
  const { data } = await readWitnessRun({
    client: await serverClient(),
    path: { run_id: runId },
    query: { ethos_run },
  });
  if (!data) {
    return (
      <>
        <PageHeader title="Witness run" />
        <Notice>This witness run could not be opened.</Notice>
      </>
    );
  }
  return <WitnessRunView data={data} />;
}
