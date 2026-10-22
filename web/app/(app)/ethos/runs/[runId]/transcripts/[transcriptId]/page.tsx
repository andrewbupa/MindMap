import Link from "next/link";

import { ResponseView } from "@/components/ethos/ResponseView";
import { Notice, PageHeader } from "@/components/ui";
import { listWitnessRuns, readWitnessTranscript, readEthosTranscript } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Ethos response view" };

export default async function EthosTranscriptPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string; transcriptId: string }>;
  searchParams: Promise<{ witness?: string }>;
}) {
  const [{ runId, transcriptId }, { witness: asked }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const { data, error, response } = await readEthosTranscript({
    client,
    path: { run_id: runId, transcript_id: transcriptId },
  });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Ethos response view" />
        <Notice>
          {response?.status === 403 && typeof detail === "string" ? detail : "This view could not be opened."}{" "}
          {response?.status === 403 ? <Link href="/settings/preferences">Your preferences</Link> : null}
        </Notice>
      </>
    );
  }
  // Signals from the witness run asked for, or the latest that read this transcript.
  const { data: runs } = await listWitnessRuns({ client, query: { source_run: data.source.id } });
  const reading = (runs ?? []).filter(
    (r) => r.run.status === "succeeded" && (r.run.config.transcripts as string[]).includes(transcriptId),
  );
  const chosen = reading.find((r) => r.run.id === asked) ?? reading[0];
  const witness = chosen
    ? (
        await readWitnessTranscript({
          client,
          path: { run_id: chosen.run.id, transcript_id: transcriptId },
        })
      ).data
    : null;
  return <ResponseView data={data} witness={witness ?? null} />;
}
