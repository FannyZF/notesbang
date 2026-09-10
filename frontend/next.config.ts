import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Standalone output keeps the production Docker image small.
  output: "standalone",
};

export default nextConfig;
