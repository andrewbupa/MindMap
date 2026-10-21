import Link from "next/link";

import { LENS_QUIET } from "@/components/lens/family";
import { Notice, PageHeader } from "@/components/ui";
import { lensQueue } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { ReviewNav } from "../ReviewNav";
import { LensQueue } from "./LensQueue";

export const metadata = { title: "Lens disagreements" };

export default async function LensReviewPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "reviewer")) {
    return (
      <>
        <PageHeader title="Lens disagreements" />
        <Notice>The review queues need the reviewer role.</Notice>
      </>
    );
  }
  const { data } = await lensQueue({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Lens disagreements" quiet={LENS_QUIET}>
        <p>
          Replies where the Lens judges differ by two points or more on a label. Record your
          verdict on each judge&apos;s finding, and the intensity you would give. Verdicts sit
          beside the findings; they never change them.
        </p>
      </PageHeader>
      <ReviewNav current="/review/lens" />
      {data.hidden_for_content_notes > 0 ? (
        <Notice>
          {data.hidden_for_content_notes} items touch self-harm, abuse or bereavement and are
          hidden. You can opt in under <Link href="/settings/preferences">your preferences</Link>.
        </Notice>
      ) : null}
      <LensQueue initial={data.items} />
    </>
  );
}
