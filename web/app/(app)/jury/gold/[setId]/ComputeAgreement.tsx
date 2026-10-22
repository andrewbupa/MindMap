"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Notice } from "@/components/ui";
import { computeGoldAgreement } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

export function ComputeAgreement({ setId }: { setId: string }) {
  const router = useRouter();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function compute() {
    setBusy(true);
    setError(null);
    const { data } = await computeGoldAgreement({ client: browserClient, path: { set_id: setId } });
    setBusy(false);
    if (!data) {
      setError("Agreement could not be computed.");
      return;
    }
    router.refresh();
  }

  return (
    <div>
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <p>
        <Button variant="secondary" onClick={compute} disabled={busy}>
          Compute agreement and update trust
        </Button>
      </p>
    </div>
  );
}
