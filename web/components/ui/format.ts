/** Plain helpers for words and numbers on screen. */

export function sentenceCase(value: string): string {
  const words = value.replaceAll("_", " ");
  return words.charAt(0).toUpperCase() + words.slice(1);
}

export function formatWhen(value: string | null | undefined, fallback = "Not recorded"): string {
  if (!value) return fallback;
  return new Intl.DateTimeFormat("en-AU", { dateStyle: "medium", timeStyle: "short" }).format(
    new Date(value),
  );
}

export function formatNumber(value: number): string {
  return Math.round(value).toLocaleString("en-GB");
}

/** Join class names, skipping empty ones. */
export function cx(...names: (string | false | null | undefined)[]): string {
  return names.filter(Boolean).join(" ");
}
