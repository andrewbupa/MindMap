"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const AREAS = [
  { href: "/", label: "Home" },
  { href: "/agents", label: "Agents" },
  { href: "/inquiry", label: "Inquiry" },
  { href: "/tally", label: "Tally" },
  { href: "/ethos", label: "Ethos" },
  { href: "/jury", label: "Jury" },
  { href: "/record", label: "Record" },
  { href: "/settings", label: "Settings" },
] as const;

/** The areas, as a groove with a raised lozenge on the current one. */
export function Nav() {
  const pathname = usePathname();
  return (
    <nav aria-label="Main">
      <ul className="ag-nav">
        {AREAS.map(({ href, label }) => {
          const active = href === "/" ? pathname === "/" : pathname.startsWith(href);
          return (
            <li key={href}>
              <Link href={href} aria-current={active ? "page" : undefined}>
                {label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}
