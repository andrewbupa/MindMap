import { Card, Notice, PageHeader } from "@/components/ui";
import { listUsers } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { UserTable } from "./UserTable";

export const metadata = { title: "Users" };

export default async function UsersPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "admin")) {
    return (
      <>
        <PageHeader title="Users" />
        <Notice>This page needs the admin role.</Notice>
      </>
    );
  }
  const { data: users } = await listUsers({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Users">
        <p>
          People appear here after their first sign-in. Changes take effect on their next request
          and are recorded in the audit log.
        </p>
      </PageHeader>
      <Card label="Users">
        <UserTable users={users} currentUserId={user.id} />
      </Card>
    </>
  );
}
