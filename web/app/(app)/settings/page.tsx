import Link from "next/link";

import { Card, PageHeader } from "@/components/ui";
import { getMe } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Settings" };

export default async function SettingsPage() {
  const user = await getMe();
  if (!user) return null;
  const admin = hasRole(user, "admin");
  return (
    <>
      <PageHeader title="Settings" />
      <Card title="Your preferences">
        <p>
          Choose whether to receive review queues that touch self-harm, abuse or bereavement.{" "}
          <Link href="/settings/preferences">Preferences</Link>
        </p>
      </Card>
      {admin ? (
        <Card title="Users and roles">
          <p>
            Grant author, reviewer, compliance and admin roles, or deactivate an account.{" "}
            <Link href="/settings/users">Users</Link>
          </p>
        </Card>
      ) : null}
      {hasRole(user, "compliance") ? (
        <Card title="Audit log">
          <p>
            Every consequential action: who launched, reviewed, exported or approved what, and when.{" "}
            <Link href="/settings/audit">Audit log</Link>
          </p>
        </Card>
      ) : null}
      {admin ? (
        <Card title="System">
          <p>
            Send a job through the queue, the worker and storage, and see the object it wrote.{" "}
            <Link href="/settings/system">System checks</Link>
          </p>
        </Card>
      ) : null}
      <Card title="Coming later">
        <p>Model roles, run budgets and provider retention notes arrive with milestones 2 and 3.</p>
      </Card>
    </>
  );
}
