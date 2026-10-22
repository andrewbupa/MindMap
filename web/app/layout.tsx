import type { Metadata } from "next";
import type { ReactNode } from "react";

import "@/styles/tokens.css";
import "./globals.css";

export const metadata: Metadata = {
  title: { default: "Agora", template: "%s · Agora" },
  description: "Tests our AI agents three ways: Explore, Measure and Lens.",
  robots: { index: false, follow: false },
};

export default function RootLayout({ children }: { children: ReactNode }) {
  return (
    <html lang="en-AU">
      <body>{children}</body>
    </html>
  );
}
