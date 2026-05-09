import type { NextConfig } from "next";

const config: NextConfig = {
  reactStrictMode: true,
  experimental: {
    typedRoutes: true,
  },
  transpilePackages: ["@agentvault/types"],
  env: {
    NEXT_PUBLIC_SOLANA_NETWORK: process.env.SOLANA_NETWORK,
    NEXT_PUBLIC_SOLANA_RPC_URL: process.env.SOLANA_RPC_URL,
    NEXT_PUBLIC_AGENTVAULT_PROGRAM_ID: process.env.AGENTVAULT_PROGRAM_ID,
    NEXT_PUBLIC_API_BASE_URL: process.env.NEXT_PUBLIC_API_BASE_URL,
    NEXT_PUBLIC_WS_BASE_URL: process.env.NEXT_PUBLIC_WS_BASE_URL,
  },
};

export default config;
