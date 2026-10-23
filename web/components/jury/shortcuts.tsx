"use client";

import {
  useEffect,
  useRef,
  useSyncExternalStore,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactNode,
} from "react";

import { Checkbox } from "@/components/ui";

export type Shortcut = {
  /** Values of KeyboardEvent.key that run it, such as "a" or "Enter". */
  keys: string[];
  /** What the key does, in a few words, for the list on screen. */
  label: string;
  run: () => void;
  /** Shown in the list but switched off, such as a key that needs a choice first. */
  disabled?: boolean;
  /** How the keys read in the list, where a row stands for several, such as "1 to 9". */
  display?: string;
};

const STORE = "agora.jury.shortcuts";
const CHANGE = "agora-shortcuts-change";

function read(): boolean {
  try {
    return window.localStorage.getItem(STORE) !== "off";
  } catch {
    return true;
  }
}

function subscribe(onChange: () => void): () => void {
  window.addEventListener(CHANGE, onChange);
  window.addEventListener("storage", onChange);
  return () => {
    window.removeEventListener(CHANGE, onChange);
    window.removeEventListener("storage", onChange);
  };
}

/** Whether single-key shortcuts are on for this viewer. They can be turned off (WCAG 2.1.4). */
export function useShortcutsOn(): [boolean, (on: boolean) => void] {
  const on = useSyncExternalStore(subscribe, read, () => true);
  const set = (value: boolean) => {
    try {
      window.localStorage.setItem(STORE, value ? "on" : "off");
    } catch {
      // Storage can be blocked; the choice then lasts until the page closes.
    }
    window.dispatchEvent(new Event(CHANGE));
  };
  return [on, set];
}

/** Keys typed into a field belong to the field. */
function typing(target: EventTarget | null): boolean {
  if (!(target instanceof HTMLElement)) return false;
  if (target.isContentEditable || target.tagName === "TEXTAREA" || target.tagName === "SELECT") return true;
  if (target instanceof HTMLInputElement) return !["radio", "checkbox", "button", "submit"].includes(target.type);
  return false;
}

/** Enter and space on a focused control keep their usual meaning. */
function activates(target: EventTarget | null, key: string): boolean {
  if (key !== "Enter" && key !== " ") return false;
  return target instanceof HTMLElement && target.closest("a, button, summary, [role=button]") !== null;
}

export function useShortcuts(on: boolean, shortcuts: Shortcut[]) {
  const latest = useRef(shortcuts);
  useEffect(() => {
    latest.current = shortcuts;
  });
  useEffect(() => {
    if (!on) return;
    function onKey(event: KeyboardEvent) {
      if (event.defaultPrevented || event.altKey || event.metaKey || event.ctrlKey) return;
      if (typing(event.target) || activates(event.target, event.key)) return;
      const found = latest.current.find((s) => !s.disabled && s.keys.includes(event.key));
      if (!found) return;
      event.preventDefault();
      found.run();
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [on]);
}

/** Leave a notes field with Escape, and record with Ctrl or Cmd and Enter. */
export function fieldKeys(onSubmit: () => void) {
  return (event: ReactKeyboardEvent<HTMLElement>) => {
    if (event.key === "Escape") {
      event.currentTarget.blur();
    } else if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
      event.preventDefault();
      onSubmit();
    }
  };
}

/** Move focus to an element by its id, such as the heading of the next item. */
export function focusOn(id: string) {
  document.getElementById(id)?.focus();
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="ag-kbd">{children}</kbd>;
}

const NAMES: Record<string, string> = {
  Enter: "Enter",
  " ": "Space",
  ArrowDown: "↓",
  ArrowUp: "↑",
  Escape: "Esc",
};

/** The keys on screen, and the switch that turns them off. */
export function ShortcutList({ shortcuts }: { shortcuts: Shortcut[] }) {
  const [on, setOn] = useShortcutsOn();
  return (
    <div className="ag-keys">
      <Checkbox label="Single-key shortcuts" checked={on} onChange={(event) => setOn(event.target.checked)} />
      {on ? (
        <dl>
          {shortcuts
            .filter((s, i) => shortcuts.findIndex((t) => t.label === s.label) === i)
            .map((s) => (
              <div key={s.label} className="ag-keys-row">
                <dt>
                  {s.display ? (
                    <Kbd>{s.display}</Kbd>
                  ) : (
                    s.keys.slice(0, 2).map((k) => <Kbd key={k}>{NAMES[k] ?? k.toUpperCase()}</Kbd>)
                  )}
                </dt>
                <dd>{s.label}</dd>
              </div>
            ))}
        </dl>
      ) : (
        <p className="ag-hint">Shortcuts are off. Every action is still a button or a field.</p>
      )}
    </div>
  );
}
