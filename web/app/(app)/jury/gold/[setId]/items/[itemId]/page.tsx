import Link from "next/link";

import { Notice, PageHeader } from "@/components/ui";
import { readGoldItem } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { LabelItem } from "./LabelItem";

export const metadata = { title: "Label a transcript" };

export default async function GoldItemPage({
  params,
}: {
  params: Promise<{ setId: string; itemId: string }>;
}) {
  const { setId, itemId } = await params;
  const { data, error, response } = await readGoldItem({
    client: await serverClient(),
    path: { set_id: setId, item_id: itemId },
  });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Label a transcript" />
        <Notice>
          {typeof detail === "string" ? detail : "This item could not be opened."}{" "}
          {response?.status === 403 ? <Link href="/settings/preferences">Your preferences</Link> : null}
        </Notice>
      </>
    );
  }
  return <LabelItem item={data} />;
}
