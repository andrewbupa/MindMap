import { Notice, PageHeader } from "@/components/ui";
import { listChecks } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { SystemChecks } from "./SystemChecks";

export const metadata = { title: "System checks" };

export default async function SystemPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "admin")) {
    return (
      <>
        <PageHeader title="System checks" />
        <Notice>This page needs the admin role.</Notice>
      </>
    );
  }
  const { data: checks } = await listChecks({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="System checks">
        <p>
          A check queues a job, the worker writes a small file to storage and reads it back, and
          the result is recorded here. Use it after each deploy.
        </p>
      </PageHeader>
      <SystemChecks initial={checks} />
    </>
  );
}
