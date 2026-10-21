import Link from "next/link";

const PAGES = [
  { href: "/review", label: "Judge scores" },
  { href: "/review/lens", label: "Lens disagreements" },
  { href: "/review/gold", label: "Gold sets" },
];

/** The review area's three queues. */
export function ReviewNav({ current }: { current: string }) {
  return (
    <nav aria-label="Review" style={{ display: "flex", gap: "var(--space-4)", marginBottom: "var(--space-4)" }}>
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
