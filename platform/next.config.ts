import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cache Components stays off. The hydration mismatch that froze the page
  // (Emotion styles rendered inline in the body) is fixed by `EmotionRegistry`,
  // but turning it on also needs the route handlers' `dynamic` exports removed
  // and every cookie read behind Suspense; not proven safe for this MVP.
  // Pages that read cookies are rendered dynamically instead.
  cacheComponents: false,

  // No page may be framed (clickjacking): the legacy header plus its CSP equivalent.
  async headers() {
    return [
      {
        source: "/:path*",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "Content-Security-Policy", value: "frame-ancestors 'none'" },
        ],
      },
    ];
  },
};


export default nextConfig;
