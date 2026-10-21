import { Placeholder } from "@/components/ui/Placeholder";

export const metadata = { title: "Reports" };

export default function ReportsPage() {
  return (
    <Placeholder title="Reports" milestone={6}>
      <p>
        Export a run or a comparison as PDF or CSV, with its full provenance: commit, config hash,
        prompt, seed, taxonomy version and the exact models used.
      </p>
    </Placeholder>
  );
}
