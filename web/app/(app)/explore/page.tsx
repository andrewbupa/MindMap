import Link from "next/link";

import { StatusBadge } from "@/components/runs/Provenance";
import { Card, PageHeader, formatWhen } from "@/components/ui";
import { listExploreRuns } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Explore" };

export default async function ExplorePage() {
  const [user, { data: runs }] = await Promise.all([
    getMe(),
    listExploreRuns({ client: await serverClient(), throwOnError: true }),
  ]);
  return (
    <>
      <PageHeader title="Explore">
        <p>
          Petri audits an agent version across many situations. An auditor model plays the member,
          our agent answers with its real prompt and tools, and a judge scores each conversation.
        </p>
      </PageHeader>
      {user && hasRole(user, "author") ? (
        <p>
          <Link href="/explore/new">Start an audit</Link>
        </p>
      ) : null}
      <Card title="Audits">
        {runs.length === 0 ? (
          <p>No audits yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Audit</th>
                <th scope="col">Status</th>
                <th scope="col">Tokens</th>
                <th scope="col">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>
                    <Link href={`/explore/runs/${run.id}`}>{run.title}</Link>
                  </td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>{run.tokens_used.toLocaleString("en-AU")}</td>
                  <td>{formatWhen(run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
