import { PageHeader } from "@/components/ui";
import { getMe } from "@/lib/api/server";

import { SensitiveOptIn } from "./SensitiveOptIn";

export const metadata = { title: "Preferences" };

export default async function PreferencesPage() {
  const user = await getMe();
  if (!user) return null;
  return (
    <>
      <PageHeader title="Preferences" />
      <SensitiveOptIn initial={user.sensitive_opt_in} />
    </>
  );
}
