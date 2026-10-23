import Link from "next/link";

import { ETHOS_NOTE } from "@/components/ethos/family";
import { RunTable } from "@/components/runs/RunTable";
import { Card, EmptyState, LinkButton, PageHeader } from "@/components/ui";
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
      <PageHeader
        title="Ethos"
        note={ETHOS_NOTE}
        actions={<LinkButton href="/ethos/taxonomy">Read the labels and expected profiles</LinkButton>}
      >
        <p>
          A panel of judges from two model families reads each of the agent&apos;s replies and marks the dispositions it
          expressed, how strongly, and whether they suited the moment. Every finding quotes the reply exactly; quotes
          that cannot be found are dropped.
        </p>
      </PageHeader>
      {user && hasRole(user, "author") ? (
        <Card title="Read a run">
          <LaunchEthos sources={sources} initial={source} />
        </Card>
      ) : null}
      <Card title="Ethos runs">
        {runs.length === 0 ? (
          <EmptyState title="No Ethos runs yet">Read a finished Inquiry or Tally run with the panel.</EmptyState>
        ) : (
          <RunTable
            runs={runs.map((item) => item.run)}
            href={(run) => `/ethos/runs/${run.id}`}
            extra={[
              {
                column: { key: "fit", label: "Mean fit", align: "right" },
                cell: (run) => {
                  const fit = runs.find((item) => item.run.id === run.id)?.mean_fit;
                  return fit === null || fit === undefined ? (
                    <span className="ag-muted">No profile</span>
                  ) : (
                    <Link href={`/ethos/runs/${run.id}#transcripts`}>{Math.round(fit * 100)}%</Link>
                  );
                },
                sort: (run) => runs.find((item) => item.run.id === run.id)?.mean_fit ?? null,
              },
            ]}
          />
        )}
      </Card>
    </>
  );
}
