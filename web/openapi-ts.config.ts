import { defineConfig } from "@hey-api/openapi-ts";

// The schema is exported from FastAPI by `make openapi`; CI fails if the
// generated client drifts from it.
export default defineConfig({
  input: "./lib/api/openapi.json",
  output: { path: "./lib/api/generated" },
  plugins: ["@hey-api/client-fetch", "@hey-api/typescript", "@hey-api/sdk"],
});
