import type { ReactNode } from "react";

import { Relief } from "./Relief";

/** Calm and specific: what is missing, in the app's own words, and the next step. */
export function EmptyState({
  title,
  action,
  children,
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
}) {
  return (
    <div className="ag-empty">
      <Relief variant="hairpin" width={240} height={100} preserve="xMidYMid meet" />
      {title ? <p className="ag-empty-title">{title}</p> : null}
      <p className="ag-empty-text">{children}</p>
      {action}
    </div>
  );
}

export function LoadingState({ label = "Loading" }: { label?: string }) {
  return (
    <div className="ag-loading" role="status" aria-live="polite">
      <span>{label}</span>
      <div className="ag-loading-track ag-channel" aria-hidden="true" />
    </div>
  );
}
