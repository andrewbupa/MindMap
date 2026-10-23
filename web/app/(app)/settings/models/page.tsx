import { DataTable } from "@/components/data/DataTable";
import { Card, Mono, PageHeader, formatNumber, sentenceCase } from "@/components/ui";
import { modelRoles } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Model roles" };

export default async function ModelsPage() {
  const { data } = await modelRoles({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Model roles">
        <p>
          The exact model behind each role, from <Mono plain>config/models.yaml</Mono>. Changing one is a reviewed
          change in git, and every run records the model IDs it used.
        </p>
      </PageHeader>
      <Card label="Model roles">
        <DataTable
          columns={[
            { key: "role", label: "Role" },
            { key: "model", label: "Model" },
            { key: "family", label: "Family" },
            { key: "settings", label: "Settings", sortable: false },
          ]}
          rows={data.roles.map((role) => ({
            id: role.role,
            cells: {
              role: sentenceCase(role.role.replaceAll("_", " ")),
              model: <Mono plain>{role.model}</Mono>,
              family: role.family,
              settings: <Mono plain>{JSON.stringify(role.generate)}</Mono>,
            },
            sort: { role: role.role, model: role.model, family: role.family },
          }))}
        />
      </Card>
      <Card title="Default token budgets">
        <DataTable
          density="dense"
          columns={[
            { key: "kind", label: "Kind of run" },
            { key: "tokens", label: "Budget", align: "right" },
          ]}
          rows={Object.entries(data.budgets).map(([kind, tokens]) => ({
            id: kind,
            cells: { kind: sentenceCase(kind), tokens: `${formatNumber(tokens)} tokens` },
            sort: { kind, tokens },
          }))}
        />
      </Card>
    </>
  );
}
