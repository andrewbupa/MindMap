import { Placeholder } from "@/components/ui/Placeholder";

export const metadata = { title: "Lens" };

export default function LensPage() {
  return (
    <Placeholder
      title="Lens"
      quiet="Lens reads expressed disposition from text. It does not see inside the model."
      milestone={5}
    >
      <p>
        See which dispositions an agent expressed in each response, how strongly, and how that
        compares with what the moment called for. Compare two prompt versions on the same
        scenarios, and follow each label across a long conversation.
      </p>
    </Placeholder>
  );
}
