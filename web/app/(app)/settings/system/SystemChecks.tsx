"use client";

import { useCallback, useState } from "react";

import {
  Badge,
  Button,
  Card,
  LinkButton,
  Mono,
  Notice,
  formatWhen,
  sentenceCase,
  type Tone,
} from "@/components/ui";
import { checkObject, launchCheck, readCheck, type SystemCheckOut } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";
import { useLiveStatus } from "@/lib/useLiveStatus";

const TONES: Record<string, Tone> = {
  queued: "neutral",
  running: "warn",
  succeeded: "ok",
  failed: "danger",
};

const isDone = (check: SystemCheckOut) => check.status === "succeeded" || check.status === "failed";

function StatusBadge({ status }: { status: string }) {
  return <Badge tone={TONES[status] ?? "neutral"}>{sentenceCase(status)}</Badge>;
}

function LiveCheck({ check }: { check: SystemCheckOut }) {
  const poll = useCallback(async () => {
    const { data } = await readCheck({ client: browserClient, path: { check_id: check.id } });
    return data ?? null;
  }, [check.id]);
  const live = useLiveStatus({
    streamUrl: `/api/system/checks/${check.id}/events`,
    poll,
    done: isDone,
    initial: check,
  });
  return <CheckRow check={live ?? check} />;
}

function CheckRow({ check }: { check: SystemCheckOut }) {
  const [error, setError] = useState<string | null>(null);
  async function openEvidence() {
    setError(null);
    const { data } = await checkObject({ client: browserClient, path: { check_id: check.id } });
    if (data) window.open(data.url, "_blank", "noopener");
    else setError("The object could not be opened.");
  }
  const detail = check.detail as { error?: string; sha256?: string; worker?: string };
  return (
    <tr>
      <td>{formatWhen(check.created_at)}</td>
      <td>
        <StatusBadge status={check.status} />
      </td>
      <td>
        {check.object_key ? (
          <LinkButton onClick={openEvidence} title="Open the object the worker wrote">
            <Mono>{check.object_key}</Mono>
          </LinkButton>
        ) : (
          (detail.error ?? "Not written yet")
        )}
        {error ? <div role="alert">{error}</div> : null}
      </td>
      <td>{detail.sha256 ? <Mono>{detail.sha256.slice(0, 12)}</Mono> : null}</td>
      <td>{detail.worker ?? null}</td>
    </tr>
  );
}

export function SystemChecks({ initial }: { initial: SystemCheckOut[] }) {
  const [checks, setChecks] = useState(initial);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function launch() {
    setBusy(true);
    setError(null);
    const { data } = await launchCheck({ client: browserClient });
    setBusy(false);
    if (!data) {
      setError("The check could not be queued.");
      return;
    }
    setChecks((current) => [data, ...current]);
  }

  return (
    <Card>
      <p>
        <Button onClick={launch} disabled={busy}>
          Run a system check
        </Button>
      </p>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      {checks.length === 0 ? (
        <p>No checks yet.</p>
      ) : (
        <table>
          <thead>
            <tr>
              <th scope="col">Started</th>
              <th scope="col">Status</th>
              <th scope="col">Object written</th>
              <th scope="col">SHA-256</th>
              <th scope="col">Worker</th>
            </tr>
          </thead>
          <tbody>
            {checks.map((check) =>
              isDone(check) ? (
                <CheckRow key={check.id} check={check} />
              ) : (
                <LiveCheck key={check.id} check={check} />
              ),
            )}
          </tbody>
        </table>
      )}
    </Card>
  );
}
