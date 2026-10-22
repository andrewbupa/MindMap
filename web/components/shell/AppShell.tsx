import Link from "next/link";
import type { ReactNode } from "react";

import { Badge, Bead } from "@/components/ui";
import type { MeOut } from "@/lib/api";
import { ROLE_LABELS } from "@/lib/auth";

import { Nav } from "./Nav";
import { SignOutButton } from "./SignOutButton";
import { ThemeSync } from "./ThemeSync";

/** The wordmark, the areas and the signed-in person, above the page. */
export function AppShell({ user, children }: { user: MeOut; children: ReactNode }) {
  const role = user.roles.includes("admin") ? "admin" : user.roles[0];
  return (
    <div className="ag-shell">
      <ThemeSync theme={user.theme} />
      <a href="#main" className="ag-skip">
        Skip to the page
      </a>
      <header className="ag-bar">
        <Link className="ag-wordmark" href="/">
          <Bead colour="var(--color-accent)" />
          Agora
        </Link>
        <Nav />
        <div className="ag-user">
          <span>{user.name}</span>
          {role ? <Badge>{ROLE_LABELS[role]}</Badge> : null}
          <SignOutButton />
        </div>
      </header>
      <main id="main" className="ag-main">
        {children}
      </main>
    </div>
  );
}
