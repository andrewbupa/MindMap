/** Ethos family colours come from tokens; intensity sets how much of the hue shows. */
export function familyColour(family: string): string {
  return `var(--family-${family}, var(--color-text-muted))`;
}

/** The share of a family's hue for an intensity, from the tokens: none at absent, then
 * faint, clear and dominant. A half step, such as a two-judge median of 1.5, sits between. */
export function intensityShare(value: number): string {
  if (!value || value <= 0) return "0%";
  const low = Math.floor(Math.min(3, value));
  const high = Math.ceil(Math.min(3, value));
  if (low === high) return `var(--intensity-${low})`;
  if (low === 0) return "calc(var(--intensity-1) / 2)";
  return `calc((var(--intensity-${low}) + var(--intensity-${high})) / 2)`;
}

/** A wash of the family hue at an intensity. */
export function tint(family: string, intensity: number): string {
  return `color-mix(in srgb, ${familyColour(family)} ${intensityShare(intensity)}, transparent)`;
}

export const INTENSITY = ["absent", "faint", "clear", "dominant"];

export function intensityName(value: number): string {
  if (value % 1) return `between ${INTENSITY[Math.floor(value)]} and ${INTENSITY[Math.ceil(value)]}`;
  return INTENSITY[Math.round(value)] ?? String(value);
}

export function labelName(key: string): string {
  const text = key.replaceAll("_", " ");
  return text.charAt(0).toUpperCase() + text.slice(1);
}

/** "1.5" for a median, "2" for a whole number. */
export function formatMedian(value: number): string {
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

export const ETHOS_NOTE = "Expressed disposition, read from text. Ethos does not see inside the model.";

/** What each kind of open-model signal is called on screen. */
export const SIGNAL_KINDS: Record<string, string> = {
  probe: "Probe",
  persona_vector: "Persona vector",
  nla: "Autoencoder explanation",
};

/**
 * A 95% interval for the difference of two shares, B minus A, from each share's Wilson
 * interval (Newcombe's hybrid score method). Shares and bounds run from 0 to 1.
 */
export function differenceInterval(
  a: { share: number; low: number; high: number },
  b: { share: number; low: number; high: number },
): { low: number; high: number } {
  const diff = b.share - a.share;
  return {
    low: diff - Math.sqrt((b.share - b.low) ** 2 + (a.high - a.share) ** 2),
    high: diff + Math.sqrt((b.high - b.share) ** 2 + (a.share - a.low) ** 2),
  };
}
