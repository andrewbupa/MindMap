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

const MONTH = new Intl.DateTimeFormat("en-AU", { month: "long", year: "numeric", timeZone: "UTC" });

/** A month such as 2026-10, as "October 2026". */
export function formatMonth(value: string): string {
  return MONTH.format(new Date(`${value}-01T00:00:00Z`));
}

/** Estimated spend in US dollars, to the cent. */
export function formatUsd(value: number): string {
  return `US$${value.toLocaleString("en-AU", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}`;
}

export function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("en-GB");
}

/** Join class names, skipping empty ones. */
export function cx(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}
