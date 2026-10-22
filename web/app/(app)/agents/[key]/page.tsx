import Link from "next/link";

import styles from "@/components/agents/agents.module.css";
import { Badge, Card, Mono, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { readAgent } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { CompareForm } from "./CompareForm";

export default async function AgentPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const { data: agent } = await readAgent({
    client: await serverClient(),
    path: { key },
    throwOnError: true,
  });
  const versions = [...agent.prompt_versions].reverse();
  return (
    <>
      <PageHeader title={agent.name}>
        <p>{agent.description}</p>
      </PageHeader>

      <Card title="Prompt versions">
        <table>
          <thead>
            <tr>
              <th scope="col">Version</th>
              <th scope="col">SHA-256</th>
              <th scope="col">Author</th>
              <th scope="col">Notes</th>
              <th scope="col">Loaded</th>
              <th scope="col">
                <span className="visually-hidden">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {versions.map((version) => (
              <tr key={version.id}>
                <td>
                  <Link href={`/agents/${agent.key}/versions/${version.version}`}>
                    {version.version}
                  </Link>
                </td>
                <td>
                  <Mono>{version.sha256.slice(0, 12)}</Mono>
                </td>
                <td>{version.author}</td>
                <td>{version.notes}</td>
                <td>{formatWhen(version.created_at)}</td>
                <td>
                  <Link href={`/agents/${agent.key}/rehearsal?version=${version.version}`}>
                    Try in rehearsal
                  </Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {versions.length > 1 ? (
          <CompareForm
            agentKey={agent.key}
            versions={agent.versions}
            defaultBase={agent.versions.at(-2) ?? agent.versions[0]!}
            defaultHead={agent.latest_version}
          />
        ) : null}
      </Card>

      <Card title="Tools">
        <p className={styles.meta}>
          Tool profile <Mono>{agent.tool_profile.sha256.slice(0, 12)}</Mono>. Calls are answered
          from synthetic fixtures: {agent.tool_profile.fixture_files.join(", ")}.
        </p>
        <table>
          <thead>
            <tr>
              <th scope="col">Tool</th>
              <th scope="col">What it does</th>
              <th scope="col">Answered from</th>
            </tr>
          </thead>
          <tbody>
            {agent.tool_profile.tools.map((tool) => {
              const fixture = tool.fixture as { file?: string; lookup?: string; respond?: unknown };
              return (
                <tr key={tool.name}>
                  <td>
                    <Mono>{tool.name}</Mono>
                  </td>
                  <td>{tool.description}</td>
                  <td>
                    {fixture.file
                      ? `${fixture.file}, by ${fixture.lookup}`
                      : "A fixed synthetic response"}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>

      <Card title="Personas">
        <p className={styles.meta}>Fictional people for testing. None of them is real.</p>
        <table>
          <thead>
            <tr>
              <th scope="col">Persona</th>
              <th scope="col">Situation</th>
              <th scope="col">Scenario type</th>
              <th scope="col">Notes</th>
            </tr>
          </thead>
          <tbody>
            {agent.personas.map((persona) => {
              const profile = persona.profile as {
                summary?: string;
                scenario_type?: string;
                content_notes?: string[];
              };
              return (
                <tr key={persona.id}>
                  <td>{persona.name}</td>
                  <td>{profile.summary}</td>
                  <td>{profile.scenario_type ? sentenceCase(profile.scenario_type) : null}</td>
                  <td>
                    {(profile.content_notes ?? []).map((note) => (
                      <Badge key={note} tone="warn">
                        Content note: {sentenceCase(note)}
                      </Badge>
                    ))}
                    {persona.risk_flags.map((flag) => (
                      <Badge key={flag}>{sentenceCase(flag)}</Badge>
                    ))}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </Card>
    </>
  );
}
