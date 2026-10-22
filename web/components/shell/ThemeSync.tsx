"use client";

import { useEffect } from "react";

import { applyTheme, type ThemeChoice } from "./theme";

/** Keeps the page, and the cookie the first paint reads, in step with the account. */
export function ThemeSync({ theme }: { theme: ThemeChoice }) {
  useEffect(() => {
    applyTheme(theme);
    if (theme !== "system") return;
    const query = window.matchMedia("(prefers-color-scheme: light)");
    const follow = () => applyTheme("system");
    query.addEventListener("change", follow);
    return () => query.removeEventListener("change", follow);
  }, [theme]);
  return null;
}
