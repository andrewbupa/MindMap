import { Placeholder } from "@/components/ui/Placeholder";

export const metadata = { title: "Agents" };

export default function AgentsPage() {
  return (
    <Placeholder title="Agents" milestone={2}>
      <p>
        Browse the agents we test, their prompt versions side by side, their tools and the
        fictional personas they meet. Chat with any prompt version in the playground, and find the
        conversation stored as an Inspect transcript.
      </p>
    </Placeholder>
  );
}
