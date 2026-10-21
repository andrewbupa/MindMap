import { StatusBadge } from "@/components/runs/Provenance";
import { Card, PageHeader, formatWhen } from "@/components/ui";
import { listExploreRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Reports" };

export default async function ReportsPage() {
  const { data: runs } = await listExploreRuns({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Reports">
        <p>
          Export a run&apos;s scores with its full provenance on every row: commit, config hash,
          prompt, seed hash, taxonomy version and the exact models. Every export is recorded in the
          audit log. PDF reports and comparisons follow.
        </p>
      </PageHeader>
      <Card title="Audits">
        {runs.length === 0 ? (
          <p>No audits yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Audit</th>
                <th scope="col">Status</th>
                <th scope="col">Started</th>
                <th scope="col">Exports</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.title}</td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>{formatWhen(run.created_at)}</td>
                  <td>
                    <a href={`/api/reports/runs/${run.id}/scores.csv`}>Scores (CSV)</a>
                    {" · "}
                    <a href={`/api/reports/runs/${run.id}/provenance`}>Provenance (JSON)</a>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
    </>
  );
}
