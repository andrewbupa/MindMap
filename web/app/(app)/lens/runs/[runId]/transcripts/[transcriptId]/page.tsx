import Link from "next/link";

import { TranscriptLens } from "@/components/lens/TranscriptLens";
import { Notice, PageHeader } from "@/components/ui";
import { listCompanionRuns, readCompanionTranscript, readLensTranscript } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Lens response view" };

export default async function LensTranscriptPage({
  params,
  searchParams,
}: {
  params: Promise<{ runId: string; transcriptId: string }>;
  searchParams: Promise<{ companion?: string }>;
}) {
  const [{ runId, transcriptId }, { companion: asked }] = await Promise.all([params, searchParams]);
  const client = await serverClient();
  const { data, error, response } = await readLensTranscript({
    client,
    path: { run_id: runId, transcript_id: transcriptId },
  });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Lens response view" />
        <Notice>
          {response?.status === 403 && typeof detail === "string" ? detail : "This view could not be opened."}{" "}
          {response?.status === 403 ? <Link href="/settings/preferences">Your preferences</Link> : null}
        </Notice>
      </>
    );
  }
  // Signals from the companion run asked for, or the latest that read this transcript.
  const { data: runs } = await listCompanionRuns({ client, query: { source_run: data.source.id } });
  const reading = (runs ?? []).filter(
    (r) => r.run.status === "succeeded" && (r.run.config.transcripts as string[]).includes(transcriptId),
  );
  const chosen = reading.find((r) => r.run.id === asked) ?? reading[0];
  const companion = chosen
    ? (
        await readCompanionTranscript({
          client,
          path: { run_id: chosen.run.id, transcript_id: transcriptId },
        })
      ).data
    : null;
  return <TranscriptLens data={data} companion={companion ?? null} />;
}
