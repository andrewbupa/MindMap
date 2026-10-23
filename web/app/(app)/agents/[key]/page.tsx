import Link from "next/link";

import { DataTable, type Row } from "@/components/data/DataTable";
import { Badge, ButtonLink, Card, LinkButton, Mono, PageHeader, formatWhen, sentenceCase } from "@/components/ui";
import { readAgent } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

import { CompareForm } from "./CompareForm";

const words = (value: string) => sentenceCase(value.replaceAll("_", " "));

export default async function AgentPage({ params }: { params: Promise<{ key: string }> }) {
  const { key } = await params;
  const { data: agent } = await readAgent({
    client: await serverClient(),
    path: { key },
    throwOnError: true,
  });
  const versions: Row[] = [...agent.prompt_versions].reverse().map((version) => ({
    id: version.id,
    cells: {
      version: <Link href={`/agents/${agent.key}/versions/${version.version}`}>{version.version}</Link>,
      sha: <Mono truncate={12}>{version.sha256}</Mono>,
      author: version.author,
      notes: <span className="ag-muted">{version.notes}</span>,
      loaded: formatWhen(version.created_at),
      try: (
        <LinkButton href={`/agents/${agent.key}/rehearsal?version=${version.version}`}>
          Try in rehearsal<span className="ag-sr">: {version.version}</span>
        </LinkButton>
      ),
    },
    sort: { version: version.created_at, author: version.author, loaded: version.created_at },
  }));
  const tools: Row[] = agent.tool_profile.tools.map((tool) => {
    const fixture = tool.fixture as { file?: string; lookup?: string; respond?: unknown };
    return {
      id: tool.name,
      cells: {
        tool: <Mono plain>{tool.name}</Mono>,
        description: tool.description,
        from: fixture.file ? (
          <>
            <Mono plain>{fixture.file}</Mono>, by {fixture.lookup}
          </>
        ) : (
          <span className="ag-muted">A fixed synthetic response</span>
        ),
      },
      sort: { tool: tool.name },
    };
  });
  const personas: Row[] = agent.personas.map((persona) => {
    const profile = persona.profile as { summary?: string; scenario_type?: string; content_notes?: string[] };
    return {
      id: persona.id,
      cells: {
        persona: persona.name,
        situation: profile.summary,
        type: profile.scenario_type ? words(profile.scenario_type) : <span className="ag-muted">None</span>,
        notes: (
          <span className="ag-row" style={{ gap: "var(--space-2)" }}>
            {(profile.content_notes ?? []).map((note) => (
              <Badge key={note} tone="warn">
                Content note: {words(note).toLowerCase()}
              </Badge>
            ))}
            {persona.risk_flags.map((flag) => (
              <Badge key={flag}>{words(flag)}</Badge>
            ))}
          </span>
        ),
      },
      sort: { persona: persona.name, type: profile.scenario_type ?? "" },
    };
  });

  return (
    <>
      <PageHeader
        title={agent.name}
        intro={agent.description}
        actions={
          <ButtonLink href={`/agents/${agent.key}/rehearsal?version=${agent.latest_version}`}>
            Try {agent.latest_version} in rehearsal
          </ButtonLink>
        }
      />

      <Card title="Prompt versions">
        <DataTable
          columns={[
            { key: "version", label: "Version" },
            { key: "sha", label: "SHA-256", sortable: false },
            { key: "author", label: "Author" },
            { key: "notes", label: "Notes", sortable: false },
            { key: "loaded", label: "Loaded", nowrap: true },
            { key: "try", label: <span className="ag-sr">Actions</span>, sortable: false },
          ]}
          rows={versions}
        />
        {agent.versions.length > 1 ? (
          <CompareForm
            agentKey={agent.key}
            versions={agent.versions}
            defaultBase={agent.versions.at(-2) ?? agent.versions[0]!}
            defaultHead={agent.latest_version}
          />
        ) : null}
      </Card>

      <Card title="Tools">
        <p className="ag-quiet">
          Tool profile <Mono truncate={12}>{agent.tool_profile.sha256}</Mono>. Calls are answered from synthetic
          fixtures: {agent.tool_profile.fixture_files.join(", ")}.
        </p>
        <DataTable
          columns={[
            { key: "tool", label: "Tool" },
            { key: "description", label: "What it does", sortable: false },
            { key: "from", label: "Answered from", sortable: false },
          ]}
          rows={tools}
        />
      </Card>

      <Card title="Personas">
        <p className="ag-quiet">Fictional people for testing. None of them is real.</p>
        <DataTable
          columns={[
            { key: "persona", label: "Persona" },
            { key: "situation", label: "Situation", sortable: false },
            { key: "type", label: "Scenario type" },
            { key: "notes", label: "Notes", sortable: false },
          ]}
          rows={personas}
          empty="This agent has no personas."
        />
      </Card>
    </>
  );
}
