import Link from "next/link";

import styles from "@/components/agents/agents.module.css";
import { Badge, PageHeader, sentenceCase } from "@/components/ui";
import { listAgents } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export const metadata = { title: "Agents" };

export default async function AgentsPage() {
  const { data: agents } = await listAgents({ client: await serverClient(), throwOnError: true });
  return (
    <>
      <PageHeader title="Agents">
        <p>
          The agents we test. Prompts, tools, fixtures and personas live in git, so every change is
          reviewed; Agora loads them on each deploy.
        </p>
      </PageHeader>
      <div className={styles.grid}>
        {agents.map((agent) => (
          <Link key={agent.key} href={`/agents/${agent.key}`} className={styles.agentCard}>
            <h2>{agent.name}</h2>
            <p className={styles.meta}>{agent.owner}</p>
            <p>{agent.description}</p>
            <p>
              {agent.domains.map((domain) => (
                <Badge key={domain}>{sentenceCase(domain)}</Badge>
              ))}
            </p>
            <p className={styles.meta}>
              {agent.versions.length} prompt versions, latest {agent.latest_version}.{" "}
              {agent.persona_count} personas.
            </p>
          </Link>
        ))}
      </div>
    </>
  );
}
