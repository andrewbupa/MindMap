import Link from "next/link";

import { familyColour, labelName } from "@/components/ethos/family";
import ethosStyles from "@/components/ethos/ethos.module.css";
import { Badge, Card, Notice, PageHeader, sentenceCase } from "@/components/ui";
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

const TONES: Record<string, "ok" | "warn" | "danger" | "neutral"> = {
  trusted: "ok",
  provisional: "warn",
  retired: "danger",
};

export default async function GoldSetPage({ params }: { params: Promise<{ setId: string }> }) {
  const { setId } = await params;
  const [user, { data: set }] = await Promise.all([
    getMe(),
    readGoldSet({ client: await serverClient(), path: { set_id: setId }, throwOnError: true }),
  ]);
  const experts = set.agreement.filter((a) => a.comparison === "expert_expert");
  const judges = [...new Set(set.agreement.filter((a) => a.judge_model).map((a) => a.judge_model!))];
  const next = set.items_list.find((item) => !item.labelled_by_me);
  return (
    <>
      <PageHeader title={set.name}>
        <p>
          {set.items} transcripts, taxonomy {set.taxonomy_version}. {set.fully_labelled} have
          been labelled by two experts; you have labelled {set.labelled_by_me}.{" "}
          {next ? <Link href={`/jury/gold/${set.id}/items/${next.id}`}>Label the next one</Link> : null}
        </p>
        {set.description ? <p>{set.description}</p> : null}
      </PageHeader>
      <JuryNav current="/jury/gold" />
      {set.hidden_for_content_notes > 0 ? (
        <Notice>
          {set.hidden_for_content_notes} items touch self-harm, abuse or bereavement and are hidden.
          You can opt in under <Link href="/settings/preferences">your preferences</Link>.
        </Notice>
      ) : null}
      <Card title="Agreement and trust">
        <p className={ethosStyles.quiet}>
          Krippendorff&apos;s alpha per label (ordinal): between experts, and between each judge and
          the experts&apos; median. A label is trusted at 0.8 or above, provisional from 0.667, and
          retired below; with too little data it stays unrated.
        </p>
        {experts.length === 0 ? <p>Agreement has not been computed yet.</p> : null}
        {experts.length ? (
          <table className={ethosStyles.numbers}>
            <thead>
              <tr>
                <th scope="col">Label</th>
                <th scope="col">Trust</th>
                <th scope="col">Experts</th>
                {judges.map((judge) => (
                  <th key={judge} scope="col">
                    {judge}
                  </th>
                ))}
                <th scope="col">Units</th>
              </tr>
            </thead>
            <tbody>
              {experts.map((row) => (
                <tr key={row.label}>
                  <td>
                    <span className={ethosStyles.swatch} style={{ background: familyColour(row.family) }} />
                    {labelName(row.label)}
                  </td>
                  <td>
                    <Badge tone={TONES[set.trust[row.label] ?? ""] ?? "neutral"}>
                      {sentenceCase(set.trust[row.label] ?? "unrated")}
                    </Badge>
                  </td>
                  <td>{alphaText(row.alpha, row.n_units)}</td>
                  {judges.map((judge) => {
                    const found = set.agreement.find((a) => a.label === row.label && a.judge_model === judge);
                    return <td key={judge}>{alphaText(found?.alpha, found?.n_units)}</td>;
                  })}
                  <td>{row.n_units}</td>
                </tr>
              ))}
            </tbody>
          </table>
        ) : null}
        {user && hasRole(user, "admin") ? <ComputeAgreement setId={set.id} /> : null}
      </Card>
      <Card title="Transcripts">
        <table>
          <thead>
            <tr>
              <th scope="col">Transcript</th>
              <th scope="col">Experts</th>
              <th scope="col">You</th>
            </tr>
          </thead>
          <tbody>
            {set.items_list.map((item) => (
              <tr key={item.id}>
                <td>
                  <Link href={`/jury/gold/${set.id}/items/${item.id}`}>
                    {sentenceCase((item.scenario_key ?? "Transcript").split("/").pop()!.replaceAll(/[-_]/g, " "))}
                  </Link>
                  {item.content_notes.map((note) => (
                    <Badge key={note} tone="warn">
                      Content note: {sentenceCase(note)}
                    </Badge>
                  ))}
                </td>
                <td>{item.labellers}</td>
                <td>{item.labelled_by_me ? "Labelled" : "Not yet"}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
