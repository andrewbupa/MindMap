"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useId, useRef, useState, type KeyboardEvent, type ReactNode } from "react";

export type Tab = { id: string; label: string; count?: number };

/** A groove of tabs with a raised lozenge on the selected one. Arrow keys move between tabs. */
export function Tabs({
  tabs,
  label,
  value,
  onChange,
  panels,
}: {
  tabs: Tab[];
  label: string;
  value?: string;
  onChange?: (id: string) => void;
  panels?: Record<string, ReactNode>;
}) {
  const [own, setOwn] = useState(value ?? tabs[0]?.id);
  const current = value ?? own;
  const base = useId();
  const refs = useRef<Record<string, HTMLButtonElement | null>>({});

  function select(id: string) {
    setOwn(id);
    onChange?.(id);
  }

  function onKey(event: KeyboardEvent<HTMLDivElement>) {
    const index = tabs.findIndex((tab) => tab.id === current);
    const next =
      event.key === "ArrowRight"
        ? (index + 1) % tabs.length
        : event.key === "ArrowLeft"
          ? (index - 1 + tabs.length) % tabs.length
          : event.key === "Home"
            ? 0
            : event.key === "End"
              ? tabs.length - 1
              : null;
    if (next === null) return;
    event.preventDefault();
    const tab = tabs[next];
    if (!tab) return;
    select(tab.id);
    refs.current[tab.id]?.focus();
  }

  return (
    <div>
      <div role="tablist" aria-label={label} className="ag-tabs" onKeyDown={onKey}>
        {tabs.map((tab) => {
          const on = tab.id === current;
          return (
            <button
              key={tab.id}
              ref={(element) => {
                refs.current[tab.id] = element;
              }}
              type="button"
              role="tab"
              id={`${base}-${tab.id}`}
              aria-selected={on}
              aria-controls={panels ? `${base}-p-${tab.id}` : undefined}
              tabIndex={on ? 0 : -1}
              className="ag-tab"
              onClick={() => select(tab.id)}
            >
              {tab.label}
              {tab.count !== undefined ? <span className="ag-count">{tab.count}</span> : null}
            </button>
          );
        })}
      </div>
      {panels && current && panels[current] !== undefined ? (
        <div
          role="tabpanel"
          id={`${base}-p-${current}`}
          aria-labelledby={`${base}-${current}`}
          className="ag-tabpanel"
          tabIndex={0}
        >
          {panels[current]}
        </div>
      ) : null}
    </div>
  );
}

/** Tabs that are pages: each is a link, and the current page carries the lozenge. */
export function TabLinks({ label, tabs }: { label: string; tabs: { href: string; label: string; count?: number }[] }) {
  const pathname = usePathname();
  const current = [...tabs]
    .sort((a, b) => b.href.length - a.href.length)
    .find((tab) => pathname === tab.href || pathname.startsWith(`${tab.href}/`));
  return (
    <nav aria-label={label}>
      <ul className="ag-tabs ag-tab-links">
        {tabs.map((tab) => (
          <li key={tab.href}>
            <Link href={tab.href} className="ag-tab" aria-current={tab === current ? "page" : undefined}>
              {tab.label}
              {tab.count !== undefined ? <span className="ag-count">{tab.count}</span> : null}
            </Link>
          </li>
        ))}
      </ul>
    </nav>
  );
}
