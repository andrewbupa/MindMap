import AxeBuilder from "@axe-core/playwright";
import type { Page } from "@playwright/test";

import { expect, seeded, test, setAccountTheme, type Seeded, type Theme } from "./fixtures";

/** Every screen, each opened on a real run, transcript or item where it needs one. */
const ROUTES: [string, (s: Seeded) => string][] = [
  ["Home", () => "/"],
  ["Agents", () => "/agents"],
  ["Agent", (s) => `/agents/${s.agent}`],
  ["Prompt version", (s) => `/agents/${s.agent}/versions/v2`],
  ["Prompt diff", (s) => `/agents/${s.agent}/diff?base=v1&head=v2`],
  ["Rehearsal launcher", (s) => `/agents/${s.agent}/rehearsal`],
  ["Rehearsal conversation", (s) => `/rehearsal/${s.rehearsal}`],
  ["Inquiry", () => "/inquiry"],
  ["Inquiry launcher", () => "/inquiry/new"],
  ["Inquiry run", (s) => `/inquiry/runs/${s.inquiryRun}`],
  ["Inquiry transcript", (s) => `/inquiry/transcripts/${s.inquiryTranscript}`],
  ["Tally", () => "/tally"],
  ["Behaviour", (s) => `/tally/behaviours/${s.behaviour}?set=${s.scenarioSet}`],
  ["Suite launcher", (s) => `/tally/new?behaviour=${s.behaviour}&set=${s.scenarioSet}`],
  ["Scenario set", (s) => `/tally/scenario-sets/${s.scenarioSet}`],
  ["Tally run", (s) => `/tally/runs/${s.tallyRun}`],
  ["Tally transcript", (s) => `/tally/transcripts/${s.tallyTranscript}`],
  ["Ethos", () => "/ethos"],
  ["Ethos taxonomy", () => "/ethos/taxonomy"],
  ["Ethos run", (s) => `/ethos/runs/${s.ethosRun}`],
  ["Ethos response view", (s) => `/ethos/runs/${s.ethosRun}/transcripts/${s.ethosTranscript}`],
  ["Jury scores", () => "/jury"],
  ["Jury Ethos disagreements", () => "/jury/ethos"],
  ["Gold sets", () => "/jury/gold"],
  ["Gold set", (s) => `/jury/gold/${s.goldSet}`],
  ["Gold labelling", (s) => `/jury/gold/${s.goldSet}/items/${s.goldItem}`],
  ["Record", () => "/record"],
  ["Settings", () => "/settings"],
  ["Preferences", () => "/settings/preferences"],
  ["Users", () => "/settings/users"],
  ["Audit log", () => "/settings/audit"],
  ["Model roles", () => "/settings/models"],
  ["API tokens", () => "/settings/tokens"],
  ["System checks", () => "/settings/system"],
];

// WCAG 2.2 A and AA, as axe-core implements them.
const TAGS = ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"];

async function open(page: Page, theme: Theme, path: string) {
  await setAccountTheme(page.request, theme);
  await page.goto(path);
  await page.waitForLoadState("networkidle");
  await expect(page.locator("html")).toHaveAttribute("data-theme", theme);
  await expect(page.locator("main#main")).toBeVisible();
}

for (const [name, path] of ROUTES) {
  test(`${name} meets WCAG 2.2 AA`, async ({ page, theme }) => {
    await open(page, theme, path(seeded()));
    // The development build adds its own overlay; it is not part of Agora.
    const results = await new AxeBuilder({ page }).withTags(TAGS).exclude("nextjs-portal").analyze();
    const found = results.violations.map(
      (v) => `${v.id} (${v.impact}): ${v.help}, at ${v.nodes.map((n) => n.target.join(" ")).slice(0, 4).join("; ")}`,
    );
    expect(found).toEqual([]);
  });
}

// At 200% zoom a 1280px window is 640 CSS pixels wide. Content reflows into one column;
// only wide tables may scroll, inside their own frame.
const REFLOW = ["Home", "Inquiry run", "Tally run", "Ethos response view", "Jury scores", "Prompt diff"];

for (const name of REFLOW) {
  test(`${name} reflows at 200% zoom`, async ({ page, theme }) => {
    await page.setViewportSize({ width: 640, height: 800 });
    const path = ROUTES.find(([route]) => route === name)![1];
    await open(page, theme, path(seeded()));
    const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
    expect(overflow).toBeLessThanOrEqual(1);
  });
}

test("Reduced motion stills every transition", async ({ page, theme }) => {
  await page.emulateMedia({ reducedMotion: "reduce" });
  await open(page, theme, "/");
  const motion = await page.evaluate(() =>
    getComputedStyle(document.documentElement).getPropertyValue("--motion-fast").trim(),
  );
  // Registered as a time, so it may read as "0s" or "0ms".
  expect(parseFloat(motion)).toBe(0);
});

test("Gold labelling rates the label in focus from the keyboard", async ({ page, theme }) => {
  const s = seeded();
  await open(page, theme, `/jury/gold/${s.goldSet}/items/${s.goldItem}`);
  const first = page.locator("input[data-rating]").first();
  const name = await first.getAttribute("name");
  await first.focus();
  // 2 rates the focused label as clear; nothing is saved until S or the button.
  await page.keyboard.press("2");
  const clear = page.locator(`input[name="${name}"][value="2"]`);
  await expect(clear).toBeChecked();
  await expect(clear).toBeFocused();
  // J moves to the next reply's heading.
  await page.keyboard.press("j");
  const focused = await page.evaluate(() => document.activeElement?.id ?? "");
  expect(focused).toMatch(/^reply-/);
});
