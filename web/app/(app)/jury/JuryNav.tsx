import Link from "next/link";

const PAGES = [
  { href: "/jury", label: "Judge scores" },
  { href: "/jury/ethos", label: "Ethos disagreements" },
  { href: "/jury/gold", label: "Gold sets" },
];

/** The review area's three queues. */
export function JuryNav({ current }: { current: string }) {
  return (
    <nav aria-label="Jury" style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-4)" }}>
      {PAGES.map((page) =>
        page.href === current ? (
          <strong key={page.href} aria-current="page">
            {page.label}
          </strong>
        ) : (
          <Link key={page.href} href={page.href}>
            {page.label}
          </Link>
        ),
      )}
    </nav>
  );
}
