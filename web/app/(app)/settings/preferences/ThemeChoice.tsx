"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { applyTheme, type ThemeChoice as Choice } from "@/components/shell/theme";
import { Card, Notice, Radio } from "@/components/ui";
import { updateMe } from "@/lib/api";
import { browserClient } from "@/lib/api/browser";

const CHOICES: { value: Choice; label: string; hint: string }[] = [
  { value: "dark", label: "Dark", hint: "The default." },
  { value: "light", label: "Light", hint: "For bright rooms and printing." },
  { value: "system", label: "Match my device", hint: "Follows your device as it changes." },
];

/** The theme is saved on your account, so it follows you to any browser you sign in on. */
export function ThemeChoice({ initial }: { initial: Choice }) {
  const router = useRouter();
  const [value, setValue] = useState(initial);
  const [error, setError] = useState<string | null>(null);

  async function change(next: Choice) {
    const before = value;
    setError(null);
    setValue(next);
    applyTheme(next);
    const { data } = await updateMe({ client: browserClient, body: { theme: next } });
    if (!data) {
      setValue(before);
      applyTheme(before);
      setError("Your theme was not saved. Please try again.");
      return;
    }
    router.refresh();
  }

  return (
    <Card title="Theme">
      {error ? <Notice tone="danger">{error}</Notice> : null}
      <fieldset className="ag-fieldset">
        <legend className="ag-sr">Theme</legend>
        <div style={{ display: "grid", gap: "var(--space-3)" }}>
          {CHOICES.map((choice) => (
            <Radio
              key={choice.value}
              name="theme"
              label={choice.label}
              hint={choice.hint}
              checked={value === choice.value}
              onChange={() => void change(choice.value)}
            />
          ))}
        </div>
      </fieldset>
    </Card>
  );
}
