import Link from "next/link";

import { Notice, PageHeader } from "@/components/ui";
import { scoreQueue } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { ReviewNav } from "./ReviewNav";
import { ScoreQueue } from "./ScoreQueue";

export const metadata = { title: "Review" };

export default async function ReviewPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "reviewer")) {
    return (
      <>
        <PageHeader title="Review" />
        <Notice>The review queues need the reviewer role.</Notice>
      </>
    );
  }
  const { data } = await scoreQueue({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Review">
        <p>
          Judge scores worth an expert&apos;s eye, highest first. Your verdict is recorded beside
          the judge&apos;s score; it never changes it.
        </p>
      </PageHeader>
      <ReviewNav current="/review" />
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
