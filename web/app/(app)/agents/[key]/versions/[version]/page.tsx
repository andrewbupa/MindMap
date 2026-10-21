import Link from "next/link";

import styles from "@/components/agents/agents.module.css";
import { Card, Mono, PageHeader, formatWhen } from "@/components/ui";
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
      <PageHeader title={`${key} ${prompt.version}`}>
        <p>
          {prompt.notes} <Link href={`/agents/${key}/playground?version=${version}`}>Try it</Link>
        </p>
      </PageHeader>
      <Card title="Provenance">
        <table>
          <tbody>
            <tr>
              <th scope="row">SHA-256 of the prompt</th>
              <td>
                <Mono>{prompt.sha256}</Mono>
              </td>
            </tr>
            <tr>
              <th scope="row">Source</th>
              <td>
                <Mono>{prompt.source_path}</Mono>, first loaded at commit{" "}
                <Mono>{prompt.git_commit.slice(0, 12)}</Mono>
              </td>
            </tr>
            <tr>
              <th scope="row">Author</th>
              <td>{prompt.author}</td>
            </tr>
            <tr>
              <th scope="row">Loaded</th>
              <td>{formatWhen(prompt.created_at)}</td>
            </tr>
          </tbody>
        </table>
      </Card>
      <Card title="System prompt, exactly as the agent receives it">
        <pre className={styles.prompt}>{prompt.text}</pre>
      </Card>
    </>
  );
}
