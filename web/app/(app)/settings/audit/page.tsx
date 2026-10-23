import { DataTable } from "@/components/data/DataTable";
import { ButtonLink, Card, Mono, Notice, PageHeader, formatWhen } from "@/components/ui";
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
      <Card label="Audit entries">
        <DataTable
          density="dense"
          columns={[
            { key: "when", label: "When", nowrap: true },
            { key: "action", label: "Action" },
            { key: "actor", label: "Actor" },
            { key: "target", label: "Target", sortable: false },
            { key: "detail", label: "Detail", sortable: false },
          ]}
          rows={data.items.map((event) => ({
            id: String(event.id),
            cells: {
              when: formatWhen(event.at),
              action: <Mono plain>{event.action}</Mono>,
              actor: event.actor_id ? <Mono truncate={8}>{event.actor_id}</Mono> : "Agora",
              target: event.target_type ? (
                <span className="ag-row" style={{ gap: "var(--space-2)" }}>
                  {event.target_type} <Mono truncate={8}>{event.target_id ?? ""}</Mono>
                </span>
              ) : null,
              detail: <Mono plain>{JSON.stringify(event.detail)}</Mono>,
            },
            sort: { when: event.at, action: event.action, actor: event.actor_id ?? "" },
          }))}
          empty="No entries yet."
        />
        {data.next_cursor ? (
          <div style={{ marginTop: "var(--space-4)" }}>
            <ButtonLink variant="secondary" href={`/settings/audit?cursor=${data.next_cursor}`}>
              Older entries
            </ButtonLink>
          </div>
        ) : null}
      </Card>
    </>
  );
}
