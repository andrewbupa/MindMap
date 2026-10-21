"use client";

import { useEffect, useRef, useState } from "react";

/**
 * Follow a resource's status over server-sent events, falling back to polling.
 *
 * App Platform closes requests after 100 seconds, so the API ends each stream
 * after 85 and the browser reconnects. If the stream errors before giving any
 * event, we poll instead.
 */
export function useLiveStatus<T extends { status: string }>({
  streamUrl,
  poll,
  done,
  initial,
  intervalMs = 2000,
}: {
  streamUrl: string | null;
  poll: () => Promise<T | null>;
  done: (value: T) => boolean;
  initial: T | null;
  intervalMs?: number;
}): T | null {
  const [value, setValue] = useState<T | null>(initial);
  const pollRef = useRef(poll);

  useEffect(() => {
    pollRef.current = poll;
  });

  useEffect(() => {
    if (!streamUrl || (initial && done(initial))) return;
    let stopped = false;
    let timer: ReturnType<typeof setTimeout> | undefined;

    const startPolling = () => {
      const tick = async () => {
        if (stopped) return;
        const next = await pollRef.current();
        if (next) setValue(next);
        if (!next || !done(next)) timer = setTimeout(tick, intervalMs);
      };
      void tick();
    };

    if (typeof EventSource === "undefined") {
      startPolling();
      return () => {
        stopped = true;
        clearTimeout(timer);
      };
    }

    let received = false;
    const source = new EventSource(streamUrl);
    source.addEventListener("status", (event) => {
      received = true;
      const next = JSON.parse((event as MessageEvent<string>).data) as T;
      setValue(next);
      if (done(next)) source.close();
    });
    source.onerror = () => {
      if (!received) {
        source.close();
        startPolling();
      }
    };
    return () => {
      stopped = true;
      source.close();
      clearTimeout(timer);
    };
  }, [streamUrl, initial, done, intervalMs]);

  return value;
}
