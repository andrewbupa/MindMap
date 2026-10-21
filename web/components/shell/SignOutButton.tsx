"use client";

import { useState } from "react";

import { Button } from "@/components/ui";
import { browserClient } from "@/lib/api/browser";
import { logout } from "@/lib/api";

export function SignOutButton() {
  const [busy, setBusy] = useState(false);
  async function signOut() {
    setBusy(true);
    const { data } = await logout({ client: browserClient });
    window.location.assign(data?.redirect ?? "/signed-out");
  }
  return (
    <Button variant="secondary" onClick={signOut} disabled={busy}>
      Sign out
    </Button>
  );
}
