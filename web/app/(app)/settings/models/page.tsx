import { DataTable } from "@/components/data/DataTable";
import { Badge, Card, Mono, PageHeader, formatDay, formatNumber, sentenceCase } from "@/components/ui";
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
      <Card title="Providers and retention">
        <p className="ag-quiet">
          Every auditor, target and judge call sends content to the provider behind its model. These terms say what each
          provider keeps. They live beside the models in <Mono plain>config/models.yaml</Mono>, and production will not
          start with a provider whose terms are missing.
        </p>
        <DataTable
          columns={[
            { key: "provider", label: "Provider" },
            { key: "roles", label: "Serves", sortable: false },
            { key: "retention", label: "Retention terms", sortable: false },
            { key: "zdr", label: "Zero data retention", sortable: false },
            { key: "confirmed", label: "Confirmed" },
          ]}
          rows={data.providers.map((provider) => ({
            id: provider.key,
            cells: {
              provider: provider.name,
              roles: provider.roles.length ? (
                provider.roles.map((role) => sentenceCase(role.replaceAll("_", " "))).join(", ")
              ) : (
                <span className="ag-muted">No role at present</span>
              ),
              retention: provider.retention,
              zdr: provider.zero_data_retention,
              confirmed: !provider.sends_content ? (
                <span className="ag-muted">Not needed</span>
              ) : provider.confirmed && provider.confirmed_on ? (
                <span>
                  {provider.confirmed_by}, {formatDay(provider.confirmed_on)}
                </span>
              ) : (
                <Badge tone="warn">To confirm</Badge>
              ),
            },
            sort: { provider: provider.name, confirmed: provider.confirmed || !provider.sends_content ? 1 : 0 },
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
