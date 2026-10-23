import type { NextConfig } from "next";

// In production App Platform's ingress sends /api to the API service, so the web
// app never sees those requests. In local development Next forwards them instead, as
// does a production build made with AGORA_FORWARD_API=1 where nothing sits in front (CI).
const apiUrl = process.env.AGORA_API_INTERNAL_URL ?? "http://localhost:8000";
const forward = process.env.NODE_ENV === "development" || process.env.AGORA_FORWARD_API === "1";

const config: NextConfig = {
  output: "standalone",
  poweredByHeader: false,
  async rewrites() {
    if (!forward) return [];
    return [{ source: "/api/:path*", destination: `${apiUrl}/api/:path*` }];
  },
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Referrer-Policy", value: "same-origin" },
          { key: "Permissions-Policy", value: "camera=(), microphone=(), geolocation=()" },
        ],
      },
    ];
  },
};

export default config;
