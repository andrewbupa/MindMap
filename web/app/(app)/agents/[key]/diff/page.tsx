import Link from "next/link";

import { DiffView, type DiffRow } from "@/components/agents/DiffView";
import { ButtonLink, Card, Mono, Notice, PageHeader } from "@/components/ui";
import { diffVersions } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Compare prompt versions" };

export default async function DiffPage({
  params,
  searchParams,
}: {
  params: Promise<{ key: string }>;
  searchParams: Promise<{ base?: string; head?: string }>;
}) {
  const { key } = await params;
  const { base, head } = await searchParams;
  if (!base || !head) {
    return (
      <>
        <PageHeader title="Compare prompt versions" />
        <Notice>
          Choose two versions to compare from <Link href={`/agents/${key}`}>the agent&apos;s page</Link>.
        </Notice>
      </>
    );
  }
  const { data: diff } = await diffVersions({
    client: await serverClient(),
    path: { key },
    query: { base, head },
    throwOnError: true,
  });
  const rows: DiffRow[] = diff.rows.map((row) => {
    const changed = row.kind === "changed";
    return {
      left: {
        n: row.left_number,
        text: row.left,
        change: row.kind === "removed" || changed ? "removed" : null,
        note: changed ? "Changed from: " : undefined,
      },
      right: {
        n: row.right_number,
        text: row.right,
        change: row.kind === "added" || changed ? "added" : null,
        note: changed ? "Changed to: " : undefined,
      },
    };
  });
  const title = (version: string, sha: string) => (
    <span className="ag-row" style={{ gap: "var(--space-2)" }}>
      <Link href={`/agents/${key}/versions/${version}`}>{version}</Link>
      <Mono truncate={12}>{sha}</Mono>
    </span>
  );
  return (
    <>
      <PageHeader
        title={`${key}: ${base} beside ${head}`}
        actions={<ButtonLink href={`/agents/${key}`} variant="secondary">Back to the agent</ButtonLink>}
      >
        <p>
          {diff.added} {diff.added === 1 ? "line" : "lines"} added, {diff.removed} removed and {diff.changed} changed.
        </p>
      </PageHeader>
      <Card label="Differences">
        <DiffView left={title(base, diff.base.sha256)} right={title(head, diff.head.sha256)} rows={rows} />
      </Card>
    </>
  );
}
