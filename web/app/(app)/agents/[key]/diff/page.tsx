import Link from "next/link";

import styles from "@/components/agents/agents.module.css";
import { Mono, Notice, PageHeader } from "@/components/ui";
import { diffVersions } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Compare prompt versions" };

const LEFT: Record<string, string> = { removed: styles.removed!, changed: styles.changedLeft! };
const RIGHT: Record<string, string> = { added: styles.added!, changed: styles.changedRight! };

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
    return <Notice>Choose two versions to compare from the agent&apos;s page.</Notice>;
  }
  const { data: diff } = await diffVersions({
    client: await serverClient(),
    path: { key },
    query: { base, head },
    throwOnError: true,
  });
  return (
    <>
      <PageHeader title={`${key}: ${base} beside ${head}`}>
        <p>
          {diff.added} lines added, {diff.removed} removed and {diff.changed} changed.{" "}
          <Link href={`/agents/${key}`}>Back to the agent</Link>
        </p>
      </PageHeader>
      <table className={styles.diff}>
        <thead>
          <tr>
            <th className={styles.lineNo} />
            <th>
              <Link href={`/agents/${key}/versions/${base}`}>{base}</Link>{" "}
              <Mono>{diff.base.sha256.slice(0, 12)}</Mono>
            </th>
            <th className={styles.lineNo} />
            <th>
              <Link href={`/agents/${key}/versions/${head}`}>{head}</Link>{" "}
              <Mono>{diff.head.sha256.slice(0, 12)}</Mono>
            </th>
          </tr>
        </thead>
        <tbody>
          {diff.rows.map((row, index) => (
            <tr key={index}>
              <td className={styles.lineNo}>{row.left_number}</td>
              <td className={LEFT[row.kind] ?? ""}>{row.left}</td>
              <td className={styles.lineNo}>{row.right_number}</td>
              <td className={RIGHT[row.kind] ?? ""}>{row.right}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
