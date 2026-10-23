import { readFileSync } from "node:fs";

import { test as base, expect, type APIRequestContext, type Page } from "@playwright/test";

export type Theme = "dark" | "light";

/** The runs and items the setup found or made, so each check can open real pages. */
export type Seeded = {
  agent: string;
  behaviour: string;
  inquiryRun: string;
  inquiryTranscript: string;
  scenarioSet: string;
  tallyRun: string;
  tallyTranscript: string;
  ethosRun: string;
  ethosTranscript: string;
  goldSet: string;
  goldItem: string;
  rehearsal: string;
};

export const STATE = "e2e/.state";
// Every write to the API carries this header; it is how the API tells the app from a form post.
export const WRITE = { "x-agora-request": "1" };

export function seeded(): Seeded {
  return JSON.parse(readFileSync(`${STATE}/seeded.json`, "utf8")) as Seeded;
}

/** Sign in at the mock identity provider as the synthetic admin. */
export async function signIn(page: Page): Promise<void> {
  await page.goto("/");
  // Signed out, the app sends us to the provider's login form; signed in, it does not.
  if (await page.locator("input[name=username]").count()) {
    await page.fill("input[name=username]", "ada");
    await page.fill("textarea[name=claims]", JSON.stringify({ email: "admin@example.test", name: "Ada Admin" }));
    await page.click("input[type=submit], button[type=submit]");
  }
  await expect(page.locator(".ag-wordmark")).toBeVisible();
}

export async function json<T>(request: APIRequestContext, path: string): Promise<T> {
  const response = await request.get(path);
  expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

export async function post<T>(request: APIRequestContext, path: string, data: unknown): Promise<T> {
  const response = await request.post(path, { data, headers: WRITE });
  expect(response.ok(), `${path}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return (await response.json()) as T;
}

/** The account's theme wins over the cookie once a page loads, so set it on the account. */
export async function setAccountTheme(request: APIRequestContext, theme: Theme): Promise<void> {
  const response = await request.patch("/api/me", { data: { theme }, headers: WRITE });
  expect(response.ok()).toBeTruthy();
}

export const test = base.extend<object, { theme: Theme }>({
  theme: ["dark", { option: true, scope: "worker" }],
});

export { expect };
