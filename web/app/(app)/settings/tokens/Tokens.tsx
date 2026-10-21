"use client";

import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Badge, Button, Card, LinkButton, Mono, Notice, formatWhen } from "@/components/ui";
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
        {error ? <Notice tone="danger">{error}</Notice> : null}
        {shown ? (
          <Notice>
            Copy this token now; it will not be shown again. Store it as a secret.
            <br />
            <Mono>{shown}</Mono>
          </Notice>
        ) : null}
        <div className={styles.inlineForm}>
          <label className={styles.field}>
            What it is for
            <input value={name} onChange={(event) => setName(event.target.value)} />
          </label>
          <Button onClick={create} disabled={!name.trim()}>
            Create token
          </Button>
        </div>
      </Card>
      <Card title="Tokens">
        <table>
          <thead>
            <tr>
              <th scope="col">Name</th>
              <th scope="col">Starts with</th>
              <th scope="col">Created</th>
              <th scope="col">Last used</th>
              <th scope="col">Status</th>
            </tr>
          </thead>
          <tbody>
            {tokens.map((token) => (
              <tr key={token.id}>
                <td>{token.name}</td>
                <td>
                  <Mono>{token.prefix}</Mono>
                </td>
                <td>{formatWhen(token.created_at)}</td>
                <td>{formatWhen(token.last_used_at, "Never")}</td>
                <td>
                  {token.revoked_at ? (
                    <Badge>Revoked</Badge>
                  ) : (
                    <>
                      <Badge tone="ok">Active</Badge>{" "}
                      <LinkButton onClick={() => revoke(token)}>Revoke</LinkButton>
                    </>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
