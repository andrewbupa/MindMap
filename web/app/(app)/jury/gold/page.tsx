import Link from "next/link";

import { Card, Notice, PageHeader, formatWhen } from "@/components/ui";
import { listGoldSets, listEthosSources } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

import { JuryNav } from "../JuryNav";
import { CreateGoldSet } from "./CreateGoldSet";

export const metadata = { title: "Gold sets" };

export default async function GoldSetsPage() {
  const user = await getMe();
  if (!user) return null;
  if (!hasRole(user, "reviewer")) {
    return (
      <>
        <PageHeader title="Gold sets" />
        <Notice>Gold-set labelling needs the reviewer role.</Notice>
      </>
    );
  }
  const client = await serverClient();
  const [{ data: sets }, { data: sources }] = await Promise.all([
    listGoldSets({ client, throwOnError: true }),
    listEthosSources({ client, throwOnError: true }),
  ]);
  return (
    <>
      <PageHeader title="Gold sets">
        <p>
          Transcripts that two experts label independently, to tally how far the Ethos labels
          can be trusted. You rate every label on every reply without seeing the judges&apos;
          findings or anyone else&apos;s ratings.
        </p>
      </PageHeader>
      <JuryNav current="/jury/gold" />
      <Card title="Gold sets">
        {sets.length === 0 ? (
          <p>No gold sets yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th scope="col">Gold set</th>
                <th scope="col">Items</th>
                <th scope="col">Labelled by two experts</th>
                <th scope="col">Labelled by you</th>
                <th scope="col">Created</th>
              </tr>
            </thead>
            <tbody>
              {sets.map((set) => (
                <tr key={set.id}>
                  <td>
                    <Link href={`/jury/gold/${set.id}`}>{set.name}</Link>
                  </td>
                  <td>{set.items}</td>
                  <td>{set.fully_labelled}</td>
                  <td>{set.labelled_by_me}</td>
                  <td>{formatWhen(set.created_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </Card>
      {hasRole(user, "admin") ? (
        <Card title="Create a gold set">
          <CreateGoldSet sources={sources} />
        </Card>
      ) : null}
    </>
  );
}
