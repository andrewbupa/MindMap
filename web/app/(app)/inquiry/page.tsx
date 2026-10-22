import { RunTable } from "@/components/runs/RunTable";
import { ButtonLink, Card, EmptyState, PageHeader } from "@/components/ui";
import { listInquiryRuns } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Inquiry" };

export default async function InquiryPage() {
  const [user, { data: runs }] = await Promise.all([
    getMe(),
    listInquiryRuns({ client: await serverClient(), throwOnError: true }),
  ]);
  const canStart = user !== null && hasRole(user, "author");
  return (
    <>
      <PageHeader
        title="Inquiry"
        intro="Petri audits an agent version across many situations. An auditor model plays the member, our agent answers with its real prompt and tools, and a judge scores each conversation."
        actions={canStart ? <ButtonLink href="/inquiry/new">Start an audit</ButtonLink> : null}
      />
      <Card title="Audits">
        {runs.length === 0 ? (
          <EmptyState title="No audits yet" action={canStart ? <ButtonLink href="/inquiry/new">Start an audit</ButtonLink> : null}>
            Choose an agent version and the seeds to audit it with.
          </EmptyState>
        ) : (
          <RunTable runs={runs} label="Audit" href={(run) => `/inquiry/runs/${run.id}`} />
        )}
      </Card>
    </>
  );
}
