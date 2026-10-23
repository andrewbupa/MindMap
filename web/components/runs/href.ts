import type { RunOut } from "@/lib/api";

export const KIND_NAMES: Record<string, string> = {
  inquiry: "Inquiry",
  tally: "Tally",
  ethos: "Ethos",
  witness: "Witness",
  rehearsal: "Rehearsal",
  scenarios: "Scenario generation",
};

/** Where a run's own page is, so a list of runs of any kind can link to each. */
export function runHref(run: Pick<RunOut, "id" | "kind" | "config">): string | null {
  switch (run.kind) {
    case "inquiry":
      return `/inquiry/runs/${run.id}`;
    case "tally":
      return `/tally/runs/${run.id}`;
    case "ethos":
      return `/ethos/runs/${run.id}`;
    case "witness":
      return `/ethos/witness/${run.id}`;
    case "rehearsal":
      return `/rehearsal/${run.id}`;
    case "scenarios":
      return typeof run.config.behaviour === "string" ? `/tally/behaviours/${run.config.behaviour}` : "/tally";
    default:
      return null;
  }
}
