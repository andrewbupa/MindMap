import { headers } from "next/headers";
import { redirect } from "next/navigation";
import type { ReactNode } from "react";

import { AppShell } from "@/components/shell/AppShell";
import { getMe } from "@/lib/api/server";
import { loginUrl } from "@/lib/auth";

export const dynamic = "force-dynamic";

export default async function SignedInLayout({ children }: { children: ReactNode }) {
  const user = await getMe();
  if (!user) {
    const path = (await headers()).get("x-agora-path") ?? "/";
    redirect(loginUrl(path));
  }
  return <AppShell user={user}>{children}</AppShell>;
}
