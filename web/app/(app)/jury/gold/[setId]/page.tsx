import Link from "next/link";

import { DataTable, type Column, type Row } from "@/components/data/DataTable";
import { LabelChip, TrustBadge } from "@/components/ethos/LabelChip";
import { Badge, ButtonLink, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
import { readGoldSet } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { JuryNav } from "../../JuryNav";
import { ComputeAgreement } from "./ComputeAgreement";

export const metadata = { title: "Gold set" };

/** Alpha, or why there is none: no paired ratings, or every rating the same. */
function alphaText(value: number | null | undefined, units = 0): string {
  if (value !== null && value !== undefined) return value.toFixed(2);
  return units > 0 ? "All ratings the same" : "Not enough data";
}

export default async function GoldSetPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = await params;
  const [user, { data: set }] = await Promise.all([
    getMe(),
    readGoldSet({ client: await serverClient(), path: { set_id: setId }, throwOnError: true }),
  ]);
  const experts = set.agreement.filter((a) => a.comparison === "expert_expert");
  const judges = [...new Set(set.agreement.filter((a) => a.judge_model).map((a) => a.judge_model!))];
  const next = set.items_list.find((item) => !item.labelled_by_me);
  const columns: Column[] = [
    { key: "label", label: "Label" },
    { key: "trust", label: "Trust" },
    { key: "experts", label: "Experts", align: "right" },
    ...judges.map((judge) => ({ key: `judge:${judge}`, label: judge, align: "right" as const })),
    { key: "units", label: "Units", align: "right" },
  ];
  const agreement: Row[] = experts.map((row) => ({
    id: row.label,
    cells: {
      label: <LabelChip family={row.family} label={row.label} />,
      trust: <TrustBadge trust={set.trust[row.label] ?? "unrated"} agreement={row.alpha} />,
      experts: <span className="ag-num">{alphaText(row.alpha, row.n_units)}</span>,
      units: row.n_units,
      ...Object.fromEntries(
        judges.map((judge) => {
          const found = set.agreement.find((a) => a.label === row.label && a.judge_model === judge);
          return [`judge:${judge}`, <span key={judge} className="ag-num">{alphaText(found?.alpha, found?.n_units)}</span>];
        }),
      ),
    },
    sort: {
      label: row.label,
      trust: set.trust[row.label] ?? "unrated",
      experts: row.alpha,
      units: row.n_units,
      ...Object.fromEntries(
        judges.map((judge) => [
          `judge:${judge}`,
          set.agreement.find((a) => a.label === row.label && a.judge_model === judge)?.alpha,
        ]),
      ),
    },
  }));
  const transcripts: Row[] = set.items_list.map((item) => ({
    id: item.id,
    cells: {
      transcript: (
        <span className="ag-row" style={{ gap: "var(--space-2)" }}>
          <Link href={`/jury/gold/${set.id}/items/${item.id}`}>
            {sentenceCase((item.scenario_key ?? "Transcript").split("/").pop()!.replaceAll(/[-_]/g, " "))}
          </Link>
          {item.content_notes.map((note) => (
            <Badge key={note} tone="warn">
              Content note: {sentenceCase(note.replaceAll("_", " ")).toLowerCase()}
            </Badge>
          ))}
        </span>
      ),
      experts: item.labellers,
      you: item.labelled_by_me ? <Badge tone="ok">Labelled</Badge> : <span className="ag-muted">Not yet</span>,
    },
    sort: { transcript: item.scenario_key ?? "", experts: item.labellers, you: Number(item.labelled_by_me) },
  }));
  return (
    <>
      <PageHeader
        title={set.name}
        actions={next ? <ButtonLink href={`/jury/gold/${set.id}/items/${next.id}`}>Label the next one</ButtonLink> : null}
      >
        <p>
          {set.items} transcripts, taxonomy {set.taxonomy_version}. {set.fully_labelled} have been labelled by two
          experts; you have labelled {set.labelled_by_me}.
        </p>
        {set.description ? <p>{set.description}</p> : null}
      </PageHeader>
      <JuryNav />
      {set.hidden_for_content_notes > 0 ? (
        <Notice>
          {set.hidden_for_content_notes} items touch self-harm, abuse or bereavement and are hidden.
          You can opt in under <Link href="/settings/preferences">your preferences</Link>.
        </Notice>
      ) : null}
      <Card title="Agreement and trust">
        <p className="ag-quiet">
          Krippendorff&apos;s alpha per label (ordinal): between experts, and between each judge and the experts&apos;
          median. A label is trusted at 0.8 or above, provisional from 0.667, and retired below; with too little data it
          stays unrated.
        </p>
        {experts.length === 0 ? (
          <p>Agreement has not been computed yet.</p>
        ) : (
          <DataTable columns={columns} rows={agreement} />
        )}
        {user && hasRole(user, "admin") ? <ComputeAgreement setId={set.id} /> : null}
      </Card>
      <Card title="Transcripts">
        <DataTable
          columns={[
            { key: "transcript", label: "Transcript" },
            { key: "experts", label: "Experts", align: "right" },
            { key: "you", label: "You" },
          ]}
          rows={transcripts}
          empty="Every transcript in this set is hidden by your content-note preferences."
        />
      </Card>
    </>
  );
}
