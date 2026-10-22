import { Bead, LinkButton, sentenceCase } from "@/components/ui";

/** A warning that a transcript touches a distressing topic, with the way to change who sees them. */
export function ContentNote({ topic }: { topic: string }) {
  return (
    <div className="ag-cnote" role="note">
      <Bead colour="var(--color-warn)" />
      <span>Content note: {sentenceCase(topic).toLowerCase()}</span>
      <LinkButton href="/settings/preferences">Change in Settings</LinkButton>
    </div>
  );
}
