import { defineConfig, devices } from "@playwright/test";

import type { Theme } from "./e2e/fixtures";

/**
 * Accessibility checks against a running Agora: the web app, the API, a worker with the
 * development models, and the mock identity provider. CI starts them; locally, `make dev`
 * or the stack in docs/RUNBOOK.md does. The setup project signs in and makes sure there is
 * one finished run of each kind to look at.
 */
export default defineConfig<object, { theme: Theme }>({
  testDir: "./e2e",
  // Both themes share one account setting, so the checks run one at a time.
  fullyParallel: false,
  workers: 1,
  timeout: 60_000,
  expect: { timeout: 10_000 },
  reporter: process.env.CI ? [["list"], ["html", { open: "never" }]] : "list",
  use: {
    baseURL: process.env.AGORA_WEB_URL ?? "http://localhost:3000",
    ...devices["Desktop Chrome"],
    viewport: { width: 1440, height: 1000 },
    trace: "retain-on-failure",
  },
  projects: [
    { name: "setup", testMatch: /setup\.ts/, timeout: 600_000 },
    {
      name: "dark",
      testMatch: /\.spec\.ts/,
      dependencies: ["setup"],
      use: { storageState: "e2e/.state/admin.json", colorScheme: "dark", theme: "dark" },
    },
    {
      name: "light",
      testMatch: /\.spec\.ts/,
      dependencies: ["dark"],
      use: { storageState: "e2e/.state/admin.json", colorScheme: "light", theme: "light" },
    },
  ],
});
