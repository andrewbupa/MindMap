import Link from "next/link";

import { Notice, PageHeader } from "@/components/ui";
import { listDimensions, readTranscript } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { TranscriptReader } from "./TranscriptReader";

export const metadata = { title: "Transcript" };

export default async function TranscriptPage({
  params,
}: {
  params: Promise<{ transcriptId: string }>;
}) {
  const { transcriptId } = await params;
  const client = await serverClient();
  const [{ data, error, response }, { data: dimensions }, user] = await Promise.all([
    readTranscript({ client, path: { transcript_id: transcriptId } }),
    listDimensions({ client, throwOnError: true }),
    getMe(),
  ]);
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Transcript" />
        <Notice>
          {response?.status === 403 && typeof detail === "string"
            ? detail
            : "This transcript could not be opened."}{" "}
          {response?.status === 403 ? (
            <Link href="/settings/preferences">Your preferences</Link>
          ) : null}
        </Notice>
      </>
    );
  }
  return (
    <TranscriptReader
      transcript={data}
      dimensions={dimensions}
      canReadFullThinking={user !== null && hasRole(user, "compliance")}
    />
  );
}
