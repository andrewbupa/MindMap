import type { ElicitationOut, TallyOut } from "@/lib/api";

export function percent(rate: number | null | undefined): string {
  return rate === null || rate === undefined ? "Not scored" : `${Math.round(rate * 100)}%`;
}

/** "5 of 12 rollouts", the count behind a rate. */
export function tallyText(tally: TallyOut): string {
  const rollouts = tally.rollouts === 1 ? "rollout" : "rollouts";
  return `${tally.elicited} of ${tally.rollouts} ${rollouts}`;
}

/** The range of the repetitions' rates, or why there is none. */
export function spreadText(elicitation: ElicitationOut): string {
  const { spread_low: low, spread_high: high, by_epoch: epochs } = elicitation;
  if (low === null || low === undefined || high === null || high === undefined) {
    return "No scored repetitions";
  }
  if (epochs.length < 2) return "One repetition";
  return low === high ? `${percent(low)} in every repetition` : `${percent(low)} to ${percent(high)}`;
}

export function meanText(tally: TallyOut): string {
  return tally.mean_score === null || tally.mean_score === undefined
    ? "Not scored"
    : `${tally.mean_score.toFixed(1)} of 10`;
}
