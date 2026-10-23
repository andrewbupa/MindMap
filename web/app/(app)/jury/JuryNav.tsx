import { TabLinks } from "@/components/ui";

const PAGES = [
  { href: "/jury", label: "Judge scores" },
  { href: "/jury/ethos", label: "Ethos disagreements" },
  { href: "/jury/gold", label: "Gold sets" },
];

/** The review area's three queues. */
export function JuryNav() {
  return (
    <div style={{ marginBottom: "var(--space-5)" }}>
      <TabLinks label="Jury" tabs={PAGES} />
    </div>
  );
}
