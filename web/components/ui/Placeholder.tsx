import { Card, PageHeader } from "./index";

/** An area that arrives in a later milestone. Says what it will hold, and when. */
export function Placeholder({
  title,
  quiet,
  milestone,
  children,
}: {
  title: string;
  quiet?: string;
  milestone: number;
  children: React.ReactNode;
}) {
  return (
    <>
      <PageHeader title={title} quiet={quiet} />
      <Card title={`Arrives in milestone ${milestone}`}>{children}</Card>
    </>
  );
}
