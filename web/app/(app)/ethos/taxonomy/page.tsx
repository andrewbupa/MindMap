import { ETHOS_NOTE } from "@/components/ethos/family";
import { LabelChip, TrustBadge } from "@/components/ethos/LabelChip";
import { Bead, Card, Mono, PageHeader } from "@/components/ui";
import { readTaxonomy } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Ethos labels" };

export default async function TaxonomyPage() {
  const { data } = await readTaxonomy({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Ethos labels" note={ETHOS_NOTE}>
        <p>
          Taxonomy <Mono>{data.version}</Mono>, from seeds/ethos/taxonomy.yaml. Every finding records the version it
          used. A label&apos;s trust follows expert agreement on the gold set.
        </p>
      </PageHeader>
      {data.families.map((family) => (
        <Card
          key={family.key}
          title={family.name}
          actions={
            <span className="ag-row ag-quiet" style={{ gap: "var(--space-2)" }}>
              <Bead colour={`var(--family-${family.key})`} />
              Source: {family.source}
            </span>
          }
        >
          <div style={{ display: "grid", gap: "var(--space-3)" }}>
            {data.labels
              .filter((label) => label.family === family.key)
              .map((label) => (
                <details key={label.key} id={label.key} className="ag-fold">
                  <summary>
                    <LabelChip family={label.family} label={label.key} /> <TrustBadge trust={label.trust_status} />
                  </summary>
                  <div className="ag-fold-body" style={{ whiteSpace: "normal" }}>
                    <p>{label.definition}</p>
                    <p className="ag-quiet">Shows it: {label.examples.map((e) => `“${e}”`).join(" ")}</p>
                    <p className="ag-quiet" style={{ marginBottom: 0 }}>
                      Does not: {label.counter_examples.map((e) => `“${e}”`).join(" ")}
                    </p>
                  </div>
                </details>
              ))}
          </div>
        </Card>
      ))}
    </>
  );
}
