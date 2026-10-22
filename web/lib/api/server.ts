import "server-only";

import { cookies } from "next/headers";

import { createClient, createConfig } from "./generated/client";
import { readMe } from "./generated/sdk.gen";
import type { MeOut } from "./generated/types.gen";

/**
 * A client for server components. It calls the API over App Platform's private
 * network and forwards the browser's cookies, so the API sees the same session.
 */
export async function serverClient() {
  const jar = await cookies();
  return createClient(
    createConfig({
      baseUrl: process.env.AGORA_API_INTERNAL_URL ?? "http://localhost:8000",
      headers: { cookie: jar.toString(), "x-agora-request": "1" },
      cache: "no-store",
    }),
  );
}

/** The signed-in user, or null when there is no valid session. */
export async function getMe(): Promise<MeOut | null> {
  const { data, response } = await readMe({ client: await serverClient() });
  if (response?.status === 401) return null;
  if (!data) throw new Error(`Could not reach the API (status ${response?.status ?? "none"}).`);
  return data;
}
