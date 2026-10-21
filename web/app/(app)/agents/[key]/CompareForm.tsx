"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import styles from "@/components/agents/agents.module.css";
import { Button } from "@/components/ui";

export function CompareForm({
  agentKey,
  versions,
  defaultBase,
  defaultHead,
}: {
  agentKey: string;
  versions: string[];
  defaultBase: string;
  defaultHead: string;
}) {
  const router = useRouter();
  const [base, setBase] = useState(defaultBase);
  const [head, setHead] = useState(defaultHead);
  return (
    <form
      className={styles.inlineForm}
      onSubmit={(event) => {
        event.preventDefault();
        router.push(`/agents/${agentKey}/diff?base=${base}&head=${head}`);
      }}
    >
      <label className={styles.field}>
        Compare
        <select value={base} onChange={(event) => setBase(event.target.value)}>
          {versions.map((version) => (
            <option key={version}>{version}</option>
          ))}
        </select>
      </label>
      <label className={styles.field}>
        with
        <select value={head} onChange={(event) => setHead(event.target.value)}>
          {versions.map((version) => (
            <option key={version}>{version}</option>
          ))}
        </select>
      </label>
      <Button type="submit" variant="secondary" disabled={base === head}>
        Show differences
      </Button>
    </form>
  );
}
