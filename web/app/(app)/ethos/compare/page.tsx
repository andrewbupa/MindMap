import Link from "next/link";

import { CompareView } from "@/components/ethos/CompareView";
import { ETHOS_QUIET } from "@/components/ethos/family";
import { Notice, PageHeader } from "@/components/ui";
import { compareEthosRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Compare Ethos runs" };

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;
  if (!a || !b) {
    return (
      <>
        <PageHeader title="Compare" quiet={ETHOS_QUIET} />
        <Notice>
          Choose two Ethos runs to compare from a run&apos;s page in <Link href="/ethos">Ethos</Link>.
        </Notice>
      </>
    );
  }
  const { data, error } = await compareEthosRuns({ client: await serverClient(), query: { a, b } });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Compare" quiet={ETHOS_QUIET} />
        <Notice>{typeof detail === "string" ? detail : "These runs could not be compared."}</Notice>
      </>
    );
  }
  return <CompareView data={data} />;
}
