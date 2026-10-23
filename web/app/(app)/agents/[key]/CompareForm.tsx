"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Button, Select } from "@/components/ui";

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
      className="ag-form-row"
      style={{ marginTop: "var(--space-4)", alignItems: "end" }}
      onSubmit={(event) => {
        event.preventDefault();
        router.push(`/agents/${agentKey}/diff?base=${base}&head=${head}`);
      }}
    >
      <Select label="Compare" value={base} onChange={(event) => setBase(event.target.value)} options={versions} />
      <Select label="With" value={head} onChange={(event) => setHead(event.target.value)} options={versions} />
      <div>
        <Button type="submit" variant="secondary" disabled={base === head}>
          Show differences
        </Button>
      </div>
    </form>
  );
}
