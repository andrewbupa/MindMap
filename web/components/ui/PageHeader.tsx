import type { ReactNode } from "react";

import { Bead } from "./basic";
import { Relief } from "./Relief";

/**
 * Title, a short intro and an optional quiet line, with the Relief motif in its own column
 * on the right. The motif never sits under text, and hides below 900px.
 */
export function PageHeader({
  title,
  intro,
  note,
  actions,
  children,
}: {
  title: string;
  /** A short intro under the title; children are an alternative for richer text. */
  intro?: ReactNode;
  /** The quiet line, such as Ethos's fixed wording. */
  note?: string;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  const lede = intro ?? children;
  return (
    <header className="ag-ph">
      <div className="ag-ph-relief" aria-hidden="true">
        <Relief variant="route" preserve="xMidYMid meet" />
      </div>
      <div className="ag-ph-text">
        <h1>{title}</h1>
        {lede ? <div className="ag-ph-intro">{lede}</div> : null}
        {note ? (
          <p className="ag-ph-note">
            <Bead colour="var(--color-text-muted)" size={8} />
            {note}
          </p>
        ) : null}
      </div>
      {actions ? <div className="ag-ph-actions">{actions}</div> : null}
    </header>
  );
}
