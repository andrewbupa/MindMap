import Link from "next/link";

import { CompareView } from "@/components/lens/CompareView";
import { LENS_QUIET } from "@/components/lens/family";
import { Notice, PageHeader } from "@/components/ui";
import { compareLensRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Compare Lens runs" };

export default async function ComparePage({
  searchParams,
}: {
  searchParams: Promise<{ a?: string; b?: string }>;
}) {
  const { a, b } = await searchParams;
  if (!a || !b) {
    return (
      <>
        <PageHeader title="Compare" quiet={LENS_QUIET} />
        <Notice>
          Choose two Lens runs to compare from a run&apos;s page in <Link href="/lens">Lens</Link>.
        </Notice>
      </>
    );
  }
  const { data, error } = await compareLensRuns({ client: await serverClient(), query: { a, b } });
  if (!data) {
    const detail = (error as { detail?: unknown } | undefined)?.detail;
    return (
      <>
        <PageHeader title="Compare" quiet={LENS_QUIET} />
        <Notice>{typeof detail === "string" ? detail : "These runs could not be compared."}</Notice>
      </>
    );
  }
  return <CompareView data={data} />;
}
