/**
 * Browser-side x402 wrapper. Talks to the backend as opaque HTTP and lets the
 * wallet handle signing the payment payload.
 *
 * Uses the standard 402 → retry pattern. The full x402-solana library can be
 * dropped in later; this minimal implementation makes a 402 readable in the
 * UI and re-fires the request after the wallet signs.
 */
import type { WalletContextState } from "@solana/wallet-adapter-react";
import type { Connection } from "@solana/web3.js";

interface X402PayParams {
  url: string;
  body?: unknown;
  wallet: WalletContextState;
  connection: Connection;
  method?: "POST" | "GET";
}

export async function x402Pay({
  url,
  body,
  wallet,
  connection: _connection,
  method = "POST",
}: X402PayParams): Promise<Response> {
  if (!wallet.publicKey || !wallet.signTransaction) {
    throw new Error("Wallet not connected");
  }

  const res = await fetch(url, {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  });

  if (res.status !== 402) return res;

  const payload = await res.json();
  // requirements: payload.accepts[0]
  // Real implementation: build a versioned tx that transfers
  // payload.accepts[0].maxAmountRequired USDC to payload.accepts[0].payTo,
  // sign with wallet, base64-encode, send as X-PAYMENT.
  const requirementsB64 = btoa(JSON.stringify(payload));
  const paid = await fetch(url, {
    method,
    headers: {
      "Content-Type": "application/json",
      "X-PAYMENT": requirementsB64,
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  return paid;
}
