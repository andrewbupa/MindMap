import Link from "next/link";

import { ETHOS_NOTE } from "@/components/ethos/family";
import { StatusBadge } from "@/components/runs/StatusBadge";
import { Card, PageHeader, formatWhen } from "@/components/ui";
import { listEthosRuns, listEthosSources } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { LaunchEthos } from "./LaunchEthos";

export const metadata = { title: "Ethos" };

export default async function EthosPage({
  searchParams,
}: {
  searchParams: Promise<{ source?: string }>;
}) {
  const { source } = await searchParams;
  const client = await serverClient();
  const [user, { data: runs }, { data: sources }] = await Promise.all([
    getMe(),
    listEthosRuns({ client, throwOnError: true }),
    listEthosSources({ client, throwOnError: true }),
  ]);
  return (
    <>
      <PageHeader title="Ethos" note={ETHOS_NOTE}>
        <p>
          A panel of judges from two model families reads each of the agent&apos;s replies and
          marks the dispositions it expressed, how strongly, and whether they suited the moment.
          Every finding quotes the reply exactly; quotes that cannot be found are dropped.{" "}
          <Link href="/ethos/taxonomy">The labels</Link>
        </p>
      </PageHeader>
      {user && hasRole(user, "author") ? (
        <Card title="Read a run">
          <LaunchEthos sources={sources} initial={source} />
        </Card>
      ) : null}
      <Card title="Ethos runs">
        {runs.length === 0 ? (
          <p>No Ethos runs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Status</th>
                <th scope="col">Mean fit</th>
                <th scope="col">Started</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((item) => (
                <tr key={item.run.id}>
                  <td>
                    <Link href={`/ethos/runs/${item.run.id}`}>{item.run.title}</Link>
                  </td>
                  <td>
                    <StatusBadge status={item.run.status} />
                  </td>
                  <td>
                    {item.mean_fit === null || item.mean_fit === undefined ? (
                      "No profile"
                    ) : (
                      <Link href={`/ethos/runs/${item.run.id}#transcripts`}>
                        {Math.round(item.mean_fit * 100)}%
                      </Link>
                    )}
                  </td>
                  <td>{formatWhen(item.run.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
