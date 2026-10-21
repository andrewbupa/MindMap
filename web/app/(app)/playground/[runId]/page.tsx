import { readConversation } from "@/lib/api";
import { getMe, serverClient } from "@/lib/api/server";

import { Conversation } from "./Conversation";

export const metadata = { title: "Playground" };

export default async function ConversationPage({ params }: { params: Promise<{ runId: string }> }) {
  const { runId } = await params;
  const [user, { data }] = await Promise.all([
    getMe(),
    readConversation({ client: await serverClient(), path: { run_id: runId }, throwOnError: true }),
  ]);
  return <Conversation initial={data} canWrite={data.run.launched_by === user?.id} />;
}
