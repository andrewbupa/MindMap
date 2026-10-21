import { Placeholder } from "@/components/ui/Placeholder";

export const metadata = { title: "Review" };

export default function ReviewPage() {
  return (
    <Placeholder title="Review" milestone={6}>
      <p>
        Expert queues for judge scores and Lens findings, and independent labelling of the gold
        set. Queues touching self-harm, abuse or bereavement are opt-in; you can choose in{" "}
        <a href="/settings/preferences">your preferences</a>.
      </p>
    </Placeholder>
  );
}
