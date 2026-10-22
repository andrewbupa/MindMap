import Link from "next/link";
import type { ReactNode } from "react";

import type { MeOut } from "@/lib/api";

import { Nav } from "./Nav";
import { SignOutButton } from "./SignOutButton";
import styles from "./shell.module.css";

export function AppShell({ user, children }: { user: MeOut; children: ReactNode }) {
  return (
    <div className={styles.shell}>
      <header className={styles.bar}>
        <Link href="/" className={styles.brand}>
          Agora
        </Link>
        <Nav />
        <div className={styles.user}>
          <span>{user.name}</span>
          <SignOutButton />
        </div>
      </header>
      <main className={styles.main}>{children}</main>
    </div>
  );
}
