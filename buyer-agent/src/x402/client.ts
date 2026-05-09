import type { Connection, Keypair } from "@solana/web3.js";

export interface X402FetchParams {
  url: string;
  method?: string;
  body?: any;
}

export interface X402FetchResult {
  response: string;
  txSignature: string;
  queriesRemaining?: number;
}

/**
 * Hackathon-mode x402 client. The full x402-fetch package wires Solana
 * payment construction; here we provide the same surface so the agent
 * code reads naturally, with a graceful fallback when the facilitator
 * isn't reachable.
 */
export class X402Client {
  constructor(public connection: Connection, public wallet: Keypair) {}

  async fetch(params: X402FetchParams): Promise<X402FetchResult> {
    const r = await fetch(params.url, {
      method: params.method ?? "POST",
      headers: { "Content-Type": "application/json" },
      body: params.body ? JSON.stringify(params.body) : undefined,
    });
    if (r.status === 402) {
      // Re-fire with a placeholder header so the backend's hackathon-mode
      // verifier accepts the request. Swap with a real x402 client when
      // facilitator credentials land.
      const requirements = await r.text();
      const paid = await fetch(params.url, {
        method: params.method ?? "POST",
        headers: {
          "Content-Type": "application/json",
          "X-PAYMENT": Buffer.from(requirements).toString("base64"),
        },
        body: params.body ? JSON.stringify(params.body) : undefined,
      });
      const data = (await paid.json()) as {
        response: string;
        tx_signature: string;
        queries_remaining?: number;
      };
      return {
        response: data.response,
        txSignature: data.tx_signature,
        queriesRemaining: data.queries_remaining,
      };
    }
    if (!r.ok) {
      throw new Error(`x402 fetch failed: ${r.status} ${await r.text()}`);
    }
    const data = (await r.json()) as {
      response: string;
      tx_signature: string;
      queries_remaining?: number;
    };
    return {
      response: data.response,
      txSignature: data.tx_signature,
      queriesRemaining: data.queries_remaining,
    };
  }
}
