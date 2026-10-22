"use client";

/**
 * A script that runs while the page is parsed, before the first paint. React would warn
 * about a script rendered on the client, so it is inert there (as Next.js advises).
 */
export function InlineScript({ html }: { html: string }) {
  return (
    <script
      type={typeof window === "undefined" ? "text/javascript" : "text/plain"}
      suppressHydrationWarning
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
