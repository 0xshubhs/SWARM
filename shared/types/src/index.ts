/**
 * Cross-package types and Zod schemas. Imported by frontend and buyer-agent.
 * Generated Anchor IDL types belong in ./idl.ts (run `anchor build && anchor idl` to refresh).
 */

export type SolanaPubkey = string;
export type ArweaveTxId = string;

export interface MemoryListing {
  id: string;
  seller: SolanaPubkey;
  arweaveTx: ArweaveTxId;
  contentHash: string;
  priceUsdc: number;
  tags: string[];
  createdAt: string;
}

export interface SandboxQuery {
  listingId: string;
  prompt: string;
}

export interface SandboxResponse {
  listingId: string;
  response: string;
  durationMs: number;
}

export type WSEvent =
  | { type: "upload.progress"; uploadId: string; pct: number }
  | { type: "upload.complete"; uploadId: string; arweaveTx: ArweaveTxId }
  | { type: "agent.phase"; phase: 1 | 2 | 3 | 4 | 5 | 6 | 7 | 8; payload: unknown };
