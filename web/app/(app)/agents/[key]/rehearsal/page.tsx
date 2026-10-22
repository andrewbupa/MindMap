import { PageHeader } from "@/components/ui";
import { readAgent } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { StartForm } from "./StartForm";

export const metadata = { title: "Rehearsal" };

export default async function RehearsalStartPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ version?: string }>;
}) {
  const { key } = await params;
  const { version } = await searchParams;
  const { data: agent } = await readAgent({
    client: await serverClient(),
    path: { key },
    throwOnError: true,
  });
  return (
    <>
      <PageHeader title={`Rehearsal: ${agent.name}`}>
        <p>
          Chat with a prompt version as a member would. The conversation is kept as a run, with its
          prompt, model and settings recorded, and saved as an Inspect transcript when you finish.
        </p>
      </PageHeader>
      <StartForm agent={agent} initialVersion={version ?? agent.latest_version} />
    </>
  );
}
