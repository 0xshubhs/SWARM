export const USDC_DECIMALS = 6;
export const PROGRAM_ID =
  process.env.NEXT_PUBLIC_PROGRAM_ID ?? "AgntVau1tVau1tVau1tVau1tVau1tVau1tVau1tVau1";
export const USDC_MINT =
  process.env.NEXT_PUBLIC_USDC_MINT ?? "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU";
export const NETWORK = (process.env.NEXT_PUBLIC_NETWORK ?? "devnet") as
  | "devnet"
  | "mainnet-beta";
export const RPC_URL =
  process.env.NEXT_PUBLIC_RPC_URL ?? "https://api.devnet.solana.com";
export const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8000";
export const BACKEND_WS_URL =
  process.env.NEXT_PUBLIC_BACKEND_WS_URL ?? "ws://localhost:8000";
export const AGENT_WS_URL =
  process.env.NEXT_PUBLIC_AGENT_WS_URL ?? BACKEND_WS_URL;
