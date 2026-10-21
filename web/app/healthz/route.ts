// Liveness for App Platform. Answers without calling the API or needing a session.
export const dynamic = "force-dynamic";

export function GET() {
  return Response.json({ status: "ok" });
}
