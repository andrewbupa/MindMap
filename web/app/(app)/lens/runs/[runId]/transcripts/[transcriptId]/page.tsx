import Link from "next/link";

import { TranscriptLens } from "@/components/lens/TranscriptLens";
import { Notice, PageHeader } from "@/components/ui";
import { readLensTranscript } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Lens response view" };

export default async function LensTranscriptPage({
  params,
}: {
  params: Promise<{ runId: string; transcriptId: string }>;
}) {
  const { runId, transcriptId } = await params;
  const { data, error, response } = await readLensTranscript({
    client: await serverClient(),
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
  return <TranscriptLens data={data} />;
}
