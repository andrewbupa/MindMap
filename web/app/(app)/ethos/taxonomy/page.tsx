import { ETHOS_QUIET, familyColour, labelName } from "@/components/ethos/family";
import styles from "@/components/ethos/ethos.module.css";
import { Badge, Card, PageHeader, sentenceCase } from "@/components/ui";
import { readTaxonomy } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Ethos labels" };

export default async function TaxonomyPage() {
  const { data } = await readTaxonomy({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Ethos labels" quiet={ETHOS_QUIET}>
        <p>
          Taxonomy {data.version}, from seeds/ethos/taxonomy.yaml. Every finding records the
          version it used. A label&apos;s trust follows expert agreement on the gold set.
        </p>
      </PageHeader>
      {data.families.map((family) => (
        <Card key={family.key} title={family.name}>
          <p className={styles.quiet}>
            <span className={styles.swatch} style={{ background: familyColour(family.key) }} />
            Source: {family.source}
          </p>
          {data.labels
            .filter((label) => label.family === family.key)
            .map((label) => (
              <details key={label.key} id={label.key}>
                <summary>
                  {labelName(label.key)}{" "}
                  <Badge tone={label.trust_status === "trusted" ? "ok" : "neutral"}>
                    {sentenceCase(label.trust_status)}
                  </Badge>
                </summary>
                <p>{label.definition}</p>
                <p className={styles.quiet}>Shows it: {label.examples.map((e) => `“${e}”`).join(" ")}</p>
                <p className={styles.quiet}>
                  Does not: {label.counter_examples.map((e) => `“${e}”`).join(" ")}
                </p>
              </details>
            ))}
        </Card>
      ))}
    </>
  );
}
