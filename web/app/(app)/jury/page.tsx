import Link from "next/link";

import { Notice, PageHeader } from "@/components/ui";
import { scoreQueue } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { JuryNav } from "./JuryNav";
import { ScoreQueue } from "./ScoreQueue";

export const metadata = { title: "Jury" };

export default async function ReviewPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "reviewer")) {
    return (
      <>
        <PageHeader title="Jury" />
        <Notice>The review queues need the reviewer role.</Notice>
      </>
    );
  }
  const { data } = await scoreQueue({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Jury">
        <p>
          Judge scores worth an expert&apos;s eye, highest first. Your verdict is recorded beside
          the judge&apos;s score; it never changes it.
        </p>
      </PageHeader>
      <JuryNav current="/jury" />
      {data.hidden_for_content_notes > 0 ? (
        <Notice>
          {data.hidden_for_content_notes} items touch self-harm, abuse or bereavement and are
          hidden. You can opt in under <Link href="/settings/preferences">your preferences</Link>.
        </Notice>
      ) : null}
      <ScoreQueue initial={data.items} />
    </>
  );
}
