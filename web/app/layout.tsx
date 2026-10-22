import type { Metadata } from "next";
import type { ReactNode } from "react";

import { InlineScript } from "@/components/shell/InlineScript";
import { THEME_SCRIPT } from "@/components/shell/theme";

import "@/styles/tokens.css";
import "@/styles/agora.css";
import "@/styles/app.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Agora", template: "%s · Agora" },
  description: "Tests our AI agents three ways: Inquiry, Tally and Ethos.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  // Dark is the design's first theme; the script swaps in the person's choice before paint.
  return (
    <html lang="en-AU" data-theme="dark" suppressHydrationWarning>
      <head>
        <InlineScript html={THEME_SCRIPT} />
      </head>
      <body>{children}</body>
    </html>
  );
}
