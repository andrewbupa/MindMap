/** Each person's theme is saved on their account and mirrored in a cookie, so an inline
 * script can apply it before the first paint. "system" follows the device. */
export const THEME_COOKIE = "agora_theme";
export type ThemeChoice = "system" | "dark" | "light";

/** Runs in <head> before the page paints; keep it small and dependency-free. */
export const THEME_SCRIPT = `(function(){try{var m=document.cookie.match(/(?:^|; )${THEME_COOKIE}=(dark|light|system)/);var t=m?m[1]:"system";if(t==="system"){t=matchMedia("(prefers-color-scheme: light)").matches?"light":"dark"}document.documentElement.setAttribute("data-theme",t)}catch(e){}})()`;

export function resolveTheme(choice: ThemeChoice): "dark" | "light" {
  if (choice !== "system") return choice;
  return window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
}

export function applyTheme(choice: ThemeChoice): void {
  document.cookie = `${THEME_COOKIE}=${choice}; path=/; max-age=31536000; samesite=lax`;
  document.documentElement.setAttribute("data-theme", resolveTheme(choice));
}
