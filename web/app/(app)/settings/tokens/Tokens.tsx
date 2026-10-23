"use client";

import { useState } from "react";

import { DataTable } from "@/components/data/DataTable";
import { Badge, Button, Card, Field, LinkButton, Mono, Notice, formatWhen } from "@/components/ui";
import { createToken, revokeToken, type ApiTokenOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function Tokens({ initial }: { initial: ApiTokenOut[] }) {
  const [tokens, setTokens] = useState(initial);
  const [name, setName] = useState("");
  const [shown, setShown] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function create() {
    setError(null);
    const { data } = await createToken({ client: browserClient, body: { name } });
    if (!data) {
      setError("The token was not created.");
      return;
    }
    setShown(data.token);
    setName("");
    setTokens((current) => [data.details, ...current]);
  }

  async function revoke(token: ApiTokenOut) {
    const { data } = await revokeToken({ client: browserClient, path: { token_id: token.id } });
    if (data) setTokens((current) => current.map((row) => (row.id === data.id ? data : row)));
  }

  return (
    <>
      <Card title="New token">
        <div className="ag-form" style={{ maxWidth: "none" }}>
          {error ? <Notice tone="danger">{error}</Notice> : null}
          {shown ? (
            <Notice title="Copy this token now">
              It will not be shown again. Store it as a secret. <Mono plain>{shown}</Mono>
            </Notice>
          ) : null}
          <div className="ag-form-row">
            <Field label="What it is for" value={name} onChange={(event) => setName(event.target.value)} />
            <div>
              <Button onClick={create} disabled={!name.trim()}>
                Create token
              </Button>
            </div>
          </div>
        </div>
      </Card>
      <Card title="Tokens">
        <DataTable
          columns={[
            { key: "name", label: "Name" },
            { key: "prefix", label: "Starts with", sortable: false },
            { key: "created", label: "Created", nowrap: true },
            { key: "used", label: "Last used", nowrap: true },
            { key: "status", label: "Status", sortable: false },
          ]}
          rows={tokens.map((token) => ({
            id: token.id,
            cells: {
              name: token.name,
              prefix: <Mono plain>{token.prefix}</Mono>,
              created: formatWhen(token.created_at),
              used: formatWhen(token.last_used_at, "Never"),
              status: token.revoked_at ? (
                <Badge>Revoked</Badge>
              ) : (
                <span className="ag-row" style={{ gap: "var(--space-2)" }}>
                  <Badge tone="ok">Active</Badge>
                  <LinkButton onClick={() => void revoke(token)}>
                    Revoke<span className="ag-sr"> {token.name}</span>
                  </LinkButton>
                </span>
              ),
            },
            sort: { name: token.name, created: token.created_at, used: token.last_used_at ?? "" },
          }))}
          empty="No tokens yet."
        />
      </Card>
    </>
  );
}
