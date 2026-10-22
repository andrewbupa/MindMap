"use client";

import { createClient, createConfig } from "./generated/client";

/**
 * A client for the browser. Requests go to the same origin, carry the session
 * cookie, and send the header the API requires on every write.
 */
export const browserClient = createClient(
  createConfig({
    baseUrl: "",
    credentials: "same-origin",
    headers: { "x-agora-request": "1" },
  }),
);
