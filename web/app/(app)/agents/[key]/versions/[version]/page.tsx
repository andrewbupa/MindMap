import Link from "next/link";

import { ButtonLink, Card, Mono, PageHeader, formatWhen } from "@/components/ui";
import { readVersion } from "@/lib/api";
import { serverClient } from "@/lib/api/server";

export default async function VersionPage({
  params,
}: {
  params: Promise<{ key: string; version: string }>;
}) {
  const { key, version } = await params;
  const { data: prompt } = await readVersion({
    client: await serverClient(),
    path: { key, version },
    throwOnError: true,
  });
  return (
    <>
      <PageHeader
        title={`${key} ${prompt.version}`}
        intro={prompt.notes}
        actions={<ButtonLink href={`/agents/${key}/rehearsal?version=${version}`}>Try it in rehearsal</ButtonLink>}
      >
        <p>
          <Link href={`/agents/${key}`}>Every version of {key}</Link>
        </p>
      </PageHeader>
      <Card title="Provenance">
        <dl className="ag-prov">
          <dt>SHA-256 of the prompt</dt>
          <dd>
            <Mono>{prompt.sha256}</Mono>
          </dd>
          <dt>Source</dt>
          <dd>
            <Mono plain>{prompt.source_path}</Mono>, first loaded at commit <Mono truncate={12}>{prompt.git_commit}</Mono>
          </dd>
          <dt>Author</dt>
          <dd>{prompt.author}</dd>
          <dt>Loaded</dt>
          <dd>{formatWhen(prompt.created_at)}</dd>
        </dl>
      </Card>
      <Card title="System prompt, exactly as the agent receives it">
        <pre className="ag-fold-body ag-code" style={{ margin: 0 }}>
          {prompt.text}
        </pre>
      </Card>
    </>
  );
}
