import Link from "next/link";

import { DataTable } from "@/components/data/DataTable";
import { Card, EmptyState, Notice, PageHeader, formatWhen } from "@/components/ui";
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
      <JuryNav />
      <Card title="Gold sets">
        <DataTable
          columns={[
            { key: "name", label: "Gold set" },
            { key: "items", label: "Items", align: "right" },
            { key: "full", label: "Labelled by two experts", align: "right" },
            { key: "mine", label: "Labelled by you", align: "right" },
            { key: "created", label: "Created", nowrap: true },
          ]}
          rows={sets.map((set) => ({
            id: set.id,
            cells: {
              name: <Link href={`/jury/gold/${set.id}`}>{set.name}</Link>,
              items: set.items,
              full: set.fully_labelled,
              mine: set.labelled_by_me,
              created: formatWhen(set.created_at),
            },
            sort: {
              name: set.name,
              items: set.items,
              full: set.fully_labelled,
              mine: set.labelled_by_me,
              created: set.created_at,
            },
          }))}
          empty={
            <EmptyState title="No gold sets yet">
              An admin draws one from a finished run. Two experts then label each transcript without seeing the
              judges.
            </EmptyState>
          }
        />
      </Card>
      {hasRole(user, "admin") ? (
        <Card title="Create a gold set">
          <CreateGoldSet sources={sources} />
        </Card>
      ) : null}
    </>
  );
}
