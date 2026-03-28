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

  // Experiment: optimize package imports for better tree-shaking
  experimental: {
    optimizePackageImports: ["lucide-react", "@xyflow/react"],
  },
};

export default nextConfig;
