"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import styles from "./shell.module.css";

const AREAS = [
  { href: "/", label: "Home" },
  { href: "/agents", label: "Agents" },
  { href: "/explore", label: "Explore" },
  { href: "/measure", label: "Measure" },
  { href: "/lens", label: "Lens" },
  { href: "/review", label: "Review" },
  { href: "/reports", label: "Reports" },
  { href: "/settings", label: "Settings" },
] as const;

export function Nav() {
  const pathname = usePathname();
  return (
    <nav className={styles.nav} aria-label="Areas">
      {AREAS.map(({ href, label }) => {
        const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`${styles.link} ${active ? styles.active : ""}`.trim()}
            aria-current={active ? "page" : undefined}
          >
            {label}
          </Link>
        );
      })}
    </nav>
  );
}
