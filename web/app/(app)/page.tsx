import Link from "next/link";

import { Badge, Card, Notice, PageHeader } from "@/components/ui";
import { getMe } from "@/lib/api/server";
import { ROLE_LABELS, hasRole } from "@/lib/auth";

export default async function HomePage() {
  const user = await getMe();
  if (!user) return null;
  return (
    <>
      <PageHeader title={`Welcome, ${user.name}`}>
        <p>
          Agora puts our agents through simulated conversations and reports how they behave. Each
          week this page will show new runs, regressions by prompt version, and items awaiting
          review.
        </p>
      </PageHeader>

      {user.roles.length === 0 ? (
        <Notice>
          You are signed in, but you have no role yet. An admin will grant you access as an author,
          reviewer or compliance reader.
        </Notice>
      ) : (
        <p>
          Your roles:{" "}
          {user.roles.map((role) => (
            <Badge key={role}>{ROLE_LABELS[role]}</Badge>
          ))}
        </p>
      )}

      <Card title="Three ways to test an agent">
        <ul>
          <li>
            <Link href="/inquiry">Inquiry</Link> asks what could go wrong across many situations.
          </li>
          <li>
            <Link href="/tally">Tally</Link> asks how often one chosen behaviour occurs.
          </li>
          <li>
            <Link href="/ethos">Ethos</Link> asks which dispositions an agent expressed, how strongly,
            and whether they suited the moment.
          </li>
        </ul>
      </Card>

      {hasRole(user, "admin") ? (
        <Card title="For admins">
          <p>
            Grant roles in <Link href="/settings/users">Settings, users</Link>. Check that the
            queue, worker and storage are working in{" "}
            <Link href="/settings/system">Settings, system</Link>.
          </p>
        </Card>
      ) : null}
    </>
  );
}
