import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Cache Components stays off: with it on, hydrating Chakra/Emotion styles
  // inside the prerendered shell raised a hydration mismatch that froze the
  // page in React's error-stack builder (Next 16.4.5, React 19.3, Chakra 3.38).
  // Pages that read cookies are rendered dynamically instead.
  cacheComponents: false,
};

export default nextConfig;
