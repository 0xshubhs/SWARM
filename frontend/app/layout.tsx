import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import { Providers } from "./providers";
import { TopNav } from "@/components/nav/TopNav";

import "./globals.css";

const inter = Inter({ subsets: ["latin"], variable: "--font-sans", display: "swap" });
const mono = JetBrains_Mono({ subsets: ["latin"], variable: "--font-mono", display: "swap" });

export const metadata: Metadata = {
  title: "AgentVault — Memory marketplace for autonomous agents",
  description:
    "Solana-native marketplace and audit layer for AI agent memory. " +
    "Compress, anchor, trade KV cache.",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" className={`${inter.variable} ${mono.variable}`}>
      <body className="min-h-screen bg-zinc-950 text-zinc-100 antialiased font-sans">
        <Providers>
          <TopNav />
          {children}
        </Providers>
      </body>
    </html>
  );
}
