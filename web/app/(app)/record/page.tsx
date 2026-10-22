import { StatusBadge } from "@/components/runs/Provenance";
import { Card, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { listReportRuns } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Record" };

const FINISHED = new Set(["succeeded", "failed", "cancelled", "stopped_at_budget"]);

export default async function ReportsPage() {
  const { data: runs } = await listReportRuns({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Record">
        <p>
          Export a run with its full provenance: commit, config hash, prompt, seed hash, taxonomy
          version and the exact models. The PDF opens with all of it; every CSV row carries it.
          Every export is recorded in the audit log.
        </p>
      </PageHeader>
      <Card title="Runs">
        {runs.length === 0 ? (
          <p>No runs yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Run</th>
                <th scope="col">Kind</th>
                <th scope="col">Status</th>
                <th scope="col">Started</th>
                <th scope="col">Exports</th>
              </tr>
            </thead>
            <tbody>
              {runs.map((run) => (
                <tr key={run.id}>
                  <td>{run.title}</td>
                  <td>{sentenceCase(run.kind)}</td>
                  <td>
                    <StatusBadge status={run.status} />
                  </td>
                  <td>{formatWhen(run.created_at)}</td>
                  <td>
                    {FINISHED.has(run.status) ? (
                      <>
                        <a href={`/api/record/runs/${run.id}/report.pdf`}>Report (PDF)</a>
                        {run.kind === "inquiry" || run.kind === "tally" ? (
                          <>
                            {" · "}
                            <a href={`/api/record/runs/${run.id}/scores.csv`}>Scores (CSV)</a>
                          </>
                        ) : null}
                        {run.kind === "ethos" ? (
                          <>
                            {" · "}
                            <a href={`/api/record/runs/${run.id}/findings.csv`}>Findings (CSV)</a>
                          </>
                        ) : null}
                        {" · "}
                      </>
                    ) : null}
                    <a href={`/api/record/runs/${run.id}/provenance`}>Provenance (JSON)</a>
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
