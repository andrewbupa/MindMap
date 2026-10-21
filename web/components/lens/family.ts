/** Lens family colours come from tokens; intensity sets how much of the hue shows. */
export function familyColour(family: string): string {
  return `var(--family-${family}, var(--color-text-muted))`;
}

/** A wash of the family hue: faint at intensity 1, strongest at 3. */
export function tint(family: string, intensity: number): string {
  const share = Math.round(Math.max(0, Math.min(3, intensity)) * 15 + 5);
  return `color-mix(in srgb, ${familyColour(family)} ${share}%, transparent)`;
}

export const INTENSITY = ["absent", "faint", "clear", "dominant"];

export function intensityName(value: number): string {
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

export const LENS_QUIET = "Expressed disposition, read from text. Lens does not see inside the model.";
