"use client";
import dynamic from "next/dynamic";

// The wallet adapter UI button uses `window` — load only client-side.
export const WalletButton = dynamic(
  async () =>
    (await import("@solana/wallet-adapter-react-ui")).WalletMultiButton,
  { ssr: false },
);
