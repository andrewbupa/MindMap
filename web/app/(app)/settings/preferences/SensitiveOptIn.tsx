"use client";

import { useState } from "react";

import { Card, Notice } from "@/components/ui";
import { updateMe } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function SensitiveOptIn({ initial }: { initial: boolean }) {
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  async function change(next: boolean) {
    setError(null);
    const { data, error: failed } = await updateMe({
      client: browserClient,
      body: { sensitive_opt_in: next },
    });
    if (failed || !data) {
      setError("Your choice was not saved. Please try again.");
      return;
    }
    setValue(data.sensitive_opt_in);
  }

  return (
    <Card title="Sensitive review queues">
      <p>
        Some scenarios touch self-harm, abuse or bereavement. They carry a content note, and you
        only receive them in review if you opt in. You can change this at any time.
      </p>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <label>
        <input type="checkbox" checked={value} onChange={(event) => change(event.target.checked)} />{" "}
        Send me review items with sensitive content notes
      </label>
    </Card>
  );
}
