/** Plain helpers for words and numbers on screen. */

export function sentenceCase(value: string): string {
  const words = value.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

/**
 * Times read in one zone for everyone, so a page rendered on the server matches the
 * browser that hydrates it. Set NEXT_PUBLIC_AGORA_TIME_ZONE to change it.
 */
export const TIME_ZONE = process.env.NEXT_PUBLIC_AGORA_TIME_ZONE || "Australia/Sydney";

const WHEN = new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeStyle: "short", timeZone: TIME_ZONE });

export function formatWhen(value: string | null | undefined, fallback = "Not recorded"): string {
  if (!value) return fallback;
  return WHEN.format(new Date(value));
}

const DAY = new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeZone: "UTC" });

/** A calendar date with no time, such as 2026-10-23, read the same everywhere. */
export function formatDay(value: string): string {
  return DAY.format(new Date(`${value.slice(0, 10)}T00:00:00Z`));
}

export function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("en-GB");
}

/** Join class names, skipping empty ones. */
export function cx(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}
