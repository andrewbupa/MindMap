import { Notice, PageHeader } from "@/components/ui";
import { listTokens } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { Tokens } from "./Tokens";

export const metadata = { title: "API tokens" };

export default async function TokensPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "admin")) {
    return (
      <>
        <PageHeader title="API tokens" />
        <Notice>This page needs the admin role.</Notice>
      </>
    );
  }
  const { data } = await listTokens({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="API tokens">
        <p>
          Tokens let tools such as Bloom call an agent version at{" "}
          <code>/api/v1/agents/&lt;agent&gt;/&lt;version&gt;/chat/completions</code>. Each token is
          shown once. Revoke any token you no longer need.
        </p>
      </PageHeader>
      <Tokens initial={data} />
    </>
  );
}
