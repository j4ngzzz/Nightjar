import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Enable React strict mode for better development warnings
  reactStrictMode: true,

  // Image optimization
  images: {
    remotePatterns: [
      {
        protocol: "https",
        hostname: "avatars.githubusercontent.com",
      },
    ],
  },

  // Experiment: optimize package imports for better tree-shaking.
  // These packages export many modules; Next.js only bundles what's used.
  // motion/react is the correct specifier for the motion package's React entry.
  experimental: {
    optimizePackageImports: [
      "lucide-react",
      "@xyflow/react",
      "motion/react",
      "recharts",
    ],
  },
};

export default nextConfig;
