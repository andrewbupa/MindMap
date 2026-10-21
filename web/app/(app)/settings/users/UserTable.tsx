"use client";

import { useState } from "react";

import { Badge, LinkButton, Notice, formatWhen } from "@/components/ui";
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

  return (
    <>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <table>
        <thead>
          <tr>
            <th scope="col">Person</th>
            {ROLES.map((role) => (
              <th scope="col" key={role}>
                {ROLE_LABELS[role]}
              </th>
            ))}
            <th scope="col">Status</th>
            <th scope="col">Last seen</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((user) => (
            <tr key={user.id}>
              <td>
                {user.name}
                <br />
                <small>{user.email}</small>
              </td>
              {ROLES.map((role) => (
                <td key={role}>
                  <input
                    type="checkbox"
                    aria-label={`${ROLE_LABELS[role]} role for ${user.name}`}
                    checked={user.roles.includes(role)}
                    disabled={user.id === currentUserId && role === "admin"}
                    onChange={() => toggleRole(user, role)}
                  />
                </td>
              ))}
              <td>
                {user.is_active ? <Badge tone="ok">Active</Badge> : <Badge>Deactivated</Badge>}{" "}
                {user.id === currentUserId ? null : (
                  <LinkButton onClick={() => save(user, { is_active: !user.is_active })}>
                    {user.is_active ? "Deactivate" : "Reactivate"}
                  </LinkButton>
                )}
              </td>
              <td>{formatWhen(user.last_seen_at, "Not yet")}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </>
  );
}
