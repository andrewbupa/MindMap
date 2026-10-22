"use client";

import { useEffect, useId, useRef, type ReactNode } from "react";

/** A modal question with its actions. Escape closes it, and focus returns where it was. */
export function Dialog({
  title,
  open,
  onClose,
  actions,
  children,
}: {
  title: string;
  open: boolean;
  onClose: () => void;
  actions?: ReactNode;
  children?: ReactNode;
}) {
  const titleId = useId();
  const box = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const before = document.activeElement as HTMLElement | null;
    box.current?.focus();
    function onKey(event: globalThis.KeyboardEvent) {
      if (event.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      before?.focus();
    };
  }, [open, onClose]);

  if (!open) return null;
  return (
    <div className="ag-dialog-backdrop">
      <div ref={box} role="dialog" aria-modal="true" aria-labelledby={titleId} className="ag-dialog" tabIndex={-1}>
        <h2 id={titleId}>{title}</h2>
        <div className="ag-dialog-body">{children}</div>
        {actions ? <div className="ag-dialog-actions">{actions}</div> : null}
      </div>
    </div>
  );
}
