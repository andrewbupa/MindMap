"use client";

import { useState } from "react";

import { DataTable, type Row } from "@/components/data/DataTable";
import { Badge, Checkbox, LinkButton, Notice, formatWhen } from "@/components/ui";
import { updateUser, type Role, type UserOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { ROLE_LABELS } from "@/lib/auth";

const ROLES: Role[] = ["author", "reviewer", "compliance", "admin"];

export function UserTable({ users, currentUserId }: { users: UserOut[]; currentUserId: string }) {
  const [rows, setRows] = useState(users);
  const [error, setError] = useState<string | null>(null);

  async function save(user: UserOut, change: { roles?: Role[]; is_active?: boolean }) {
    setError(null);
    const { data, error: failed } = await updateUser({
      client: browserClient,
      path: { user_id: user.id },
      body: change,
    });
    if (failed || !data) {
      const detail = (failed as { detail?: unknown } | undefined)?.detail;
      setError(typeof detail === "string" ? detail : "The change was not saved.");
      return;
    }
    setRows((current) => current.map((row) => (row.id === data.id ? data : row)));
  }

  function toggleRole(user: UserOut, role: Role) {
    const roles = user.roles.includes(role)
      ? user.roles.filter((held) => held !== role)
      : [...user.roles, role];
    return save(user, { roles });
  }

  const table: Row[] = rows.map((user) => ({
    id: user.id,
    cells: {
      person: (
        <span style={{ display: "grid" }}>
          <span>{user.name}</span>
          <span className="ag-hint">{user.email}</span>
        </span>
      ),
      ...Object.fromEntries(
        ROLES.map((role) => [
          role,
          <Checkbox
            key={role}
            label={<span className="ag-sr">{`${ROLE_LABELS[role]} role for ${user.name}`}</span>}
            checked={user.roles.includes(role)}
            disabled={user.id === currentUserId && role === "admin"}
            onChange={() => void toggleRole(user, role)}
          />,
        ]),
      ),
      status: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          {user.is_active ? <Badge tone="ok">Active</Badge> : <Badge>Deactivated</Badge>}
          {user.id === currentUserId ? null : (
            <LinkButton onClick={() => void save(user, { is_active: !user.is_active })}>
              {user.is_active ? "Deactivate" : "Reactivate"}
              <span className="ag-sr"> {user.name}</span>
            </LinkButton>
          )}
        </span>
      ),
      seen: formatWhen(user.last_seen_at, "Not yet"),
    },
    sort: { person: user.name, seen: user.last_seen_at ?? "" },
  }));

  return (
    <>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <DataTable
        columns={[
          { key: "person", label: "Person" },
          ...ROLES.map((role) => ({ key: role, label: ROLE_LABELS[role], sortable: false })),
          { key: "status", label: "Status", sortable: false },
          { key: "seen", label: "Last seen", nowrap: true },
        ]}
        rows={table}
      />
    </>
  );
}
