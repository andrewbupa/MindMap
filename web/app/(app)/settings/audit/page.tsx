import Link from "next/link";

import { Mono, Notice, PageHeader, formatWhen } from "@/components/ui";
import { listEvents } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Audit log" };

export default async function AuditPage({
  searchParams,
}: {
  searchParams: Promise<{ cursor?: string }>;
}) {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "compliance")) {
    return (
      <>
        <PageHeader title="Audit log" />
        <Notice>This page needs the compliance or admin role.</Notice>
      </>
    );
  }
  const { cursor } = await searchParams;
  const { data } = await listEvents({
    client: await serverClient(),
    query: { cursor: cursor ? Number(cursor) : undefined, limit: 50 },
    throwOnError: true,
  });
  return (
    <>
      <PageHeader title="Audit log">
        <p>The log is append-only. Nobody, including admins, can edit or delete an entry.</p>
      </PageHeader>
      <table>
        <thead>
          <tr>
            <th scope="col">When</th>
            <th scope="col">Action</th>
            <th scope="col">Actor</th>
            <th scope="col">Target</th>
            <th scope="col">Detail</th>
          </tr>
        </thead>
        <tbody>
          {data.items.map((event) => (
            <tr key={event.id}>
              <td>{formatWhen(event.at)}</td>
              <td>
                <Mono>{event.action}</Mono>
              </td>
              <td>{event.actor_id ? <Mono>{event.actor_id.slice(0, 8)}</Mono> : "Agora"}</td>
              <td>
                {event.target_type ? (
                  <>
                    {event.target_type} <Mono>{event.target_id?.slice(0, 8)}</Mono>
                  </>
                ) : null}
              </td>
              <td>
                <Mono>{JSON.stringify(event.detail)}</Mono>
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {data.next_cursor ? (
        <p>
          <Link href={`/settings/audit?cursor=${data.next_cursor}`}>Older entries</Link>
        </p>
      ) : null}
    </>
  );
}
