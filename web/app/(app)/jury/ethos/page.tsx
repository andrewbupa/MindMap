import Link from "next/link";

import { ETHOS_QUIET } from "@/components/ethos/family";
import { Notice, PageHeader } from "@/components/ui";
import { ethosQueue } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { JuryNav } from "../JuryNav";
import { EthosQueue } from "./EthosQueue";

export const metadata = { title: "Ethos disagreements" };

export default async function EthosReviewPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "reviewer")) {
    return (
      <>
        <PageHeader title="Ethos disagreements" />
        <Notice>The review queues need the reviewer role.</Notice>
      </>
    );
  }
  const { data } = await ethosQueue({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Ethos disagreements" note={ETHOS_QUIET}>
        <p>
          Replies where the Ethos judges differ by two points or more on a label. Record your
          verdict on each judge&apos;s finding, and the intensity you would give. Verdicts sit
          beside the findings; they never change them.
        </p>
      </PageHeader>
      <JuryNav current="/jury/ethos" />
      {data.hidden_for_content_notes > 0 ? (
        <Notice>
          {data.hidden_for_content_notes} items touch self-harm, abuse or bereavement and are
          hidden. You can opt in under <Link href="/settings/preferences">your preferences</Link>.
        </Notice>
      ) : null}
      <EthosQueue initial={data.items} />
    </>
  );
}
