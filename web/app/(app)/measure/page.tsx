import { Placeholder } from "@/components/ui/Placeholder";

export const metadata = { title: "Measure" };

export default function MeasurePage() {
  return (
    <Placeholder title="Measure" milestone={4}>
      <p>
        Run Bloom suites for one behaviour at a time and compare its elicitation rate across prompt
        versions, with the spread across repetitions.
      </p>
    </Placeholder>
  );
}
