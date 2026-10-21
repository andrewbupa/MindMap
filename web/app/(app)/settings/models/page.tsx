import { Card, Mono, PageHeader, sentenceCase } from "@/components/ui";
import { modelRoles } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Model roles" };

export default async function ModelsPage() {
  const { data } = await modelRoles({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Model roles">
        <p>
          The exact model behind each role, from <Mono>config/models.yaml</Mono>. Changing one is a
          reviewed change in git, and every run records the model IDs it used.
        </p>
      </PageHeader>
      <Card>
        <table>
          <thead>
            <tr>
              <th scope="col">Role</th>
              <th scope="col">Model</th>
              <th scope="col">Family</th>
              <th scope="col">Settings</th>
            </tr>
          </thead>
          <tbody>
            {data.roles.map((role) => (
              <tr key={role.role}>
                <td>{sentenceCase(role.role)}</td>
                <td>
                  <Mono>{role.model}</Mono>
                </td>
                <td>{role.family}</td>
                <td>
                  <Mono>{JSON.stringify(role.generate)}</Mono>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card title="Default token budgets">
        <table>
          <tbody>
            {Object.entries(data.budgets).map(([kind, tokens]) => (
              <tr key={kind}>
                <th scope="row">{sentenceCase(kind)}</th>
                <td>{tokens.toLocaleString("en-AU")} tokens</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </>
  );
}
