import Link from "next/link";

import { Card, PageHeader } from "@/components/ui";
import { getMe } from "@/lib/api/server";
import { hasRole } from "@/lib/auth";

export const metadata = { title: "Settings" };

type Page = { href: string; title: string; text: string; show: boolean };

export default async function SettingsPage() {
  const user = await getMe();
  if (!user) return null;
  const admin = hasRole(user, "admin");
  const pages: Page[] = [
    {
      href: "/settings/preferences",
      title: "Your preferences",
      text: "Your theme, and whether to receive review items that touch self-harm, abuse or bereavement.",
      show: true,
    },
    {
      href: "/settings/users",
      title: "Users and roles",
      text: "Grant author, reviewer, compliance and admin roles, or deactivate an account.",
      show: admin,
    },
    {
      href: "/settings/audit",
      title: "Audit log",
      text: "Every consequential action: who launched, reviewed, exported or approved what, and when.",
      show: hasRole(user, "compliance"),
    },
    {
      href: "/settings/system",
      title: "System checks",
      text: "Send a job through the queue, the worker and storage, and see the object it wrote.",
      show: admin,
    },
    {
      href: "/settings/spend",
      title: "Spend",
      text: "Estimated cost by month and by kind of run, linked to the runs behind it.",
      show: true,
    },
    {
      href: "/settings/models",
      title: "Model roles and budgets",
      text: "The exact model behind each role, and the default token budget for each kind of run.",
      show: true,
    },
    {
      href: "/settings/tokens",
      title: "API tokens",
      text: "Issue and revoke tokens for tools that call an agent version directly.",
      show: admin,
    },
  ];
  return (
    <>
      <PageHeader title="Settings" />
      <div className="ag-tiles">
        {pages
          .filter((page) => page.show)
          .map((page) => (
            <Card key={page.href} className="ag-tile">
              <h2 className="ag-card-title">
                <Link href={page.href} className="ag-tile-link">
                  {page.title}
                </Link>
              </h2>
              <p className="ag-quiet" style={{ marginBottom: 0 }}>
                {page.text}
              </p>
            </Card>
          ))}
      </div>
    </>
  );
}
