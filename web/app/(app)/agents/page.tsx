import Link from "next/link";

import { Badge, Card, EmptyState, PageHeader, sentenceCase } from "@/components/ui";
import { listAgents } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Agents" };

export default async function AgentsPage() {
  const { data: agents } = await listAgents({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader
        title="Agents"
        intro="The agents we test. Prompts, tools, fixtures and personas live in git, so every change is reviewed; Agora loads them on each deploy."
      />
      {agents.length === 0 ? (
        <EmptyState title="No agents yet">Add one under agents/ in the repository, then deploy.</EmptyState>
      ) : (
        <div className="ag-tiles">
          {agents.map((agent) => (
            <Card key={agent.key} className="ag-tile">
              <h2 className="ag-card-title">
                <Link href={`/agents/${agent.key}`} className="ag-tile-link">
                  {agent.name}
                </Link>
              </h2>
              <p className="ag-quiet" style={{ margin: "var(--space-1) 0 var(--space-3)" }}>
                {agent.owner}
              </p>
              <p>{agent.description}</p>
              <p className="ag-row" style={{ gap: "var(--space-2)" }}>
                {agent.domains.map((domain) => (
                  <Badge key={domain}>{sentenceCase(domain)}</Badge>
                ))}
              </p>
              <p className="ag-quiet" style={{ marginBottom: 0 }}>
                {agent.versions.length} prompt {agent.versions.length === 1 ? "version" : "versions"}, latest{" "}
                {agent.latest_version}. {agent.persona_count} {agent.persona_count === 1 ? "persona" : "personas"}.
              </p>
            </Card>
          ))}
        </div>
      )}
    </>
  );
}
