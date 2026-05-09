import type { Listing, TaskResult, AgentRunOptions, ListingPreview } from "@agentvault/types";
import type { LLMClient } from "@agentvault/types/llm";

export type { Listing, TaskResult, AgentRunOptions, ListingPreview, LLMClient };

export interface NarratorEventMap {
  start: { task: string; budget_usdc: number };
  classify: { tags: string[]; reasoning?: string; domain?: string };
  discover: Listing[];
  sandboxStart: { listing_id: string; query: string };
  sandboxX402: { listing_id: string; tx_signature: string; amount_usdc: number };
  sandboxResponse: { listing_id: string; response: string; score: number };
  decision: { winner_id: string; reasoning: string; score: number };
  purchaseSigning: { listing_id: string };
  purchaseConfirmed: { tx_signature: string; license_pda: string };
  fetchProgress: number;
  fetchDone: { arweave_tx: string; bytes: number };
  verifyHash: { hash_hex: string; verified: boolean };
  decompress: { decompressed_size_mb: number; load_time_ms: number };
  executeStart: { prompt: string };
  executeToken: string;
  executeDone: { output: string; total_tokens: number };
  complete: { total_cost_usdc: number; duration_ms: number };
  warn: string;
  error: { phase: string; error: string };
}

export interface Narrator {
  start(d: NarratorEventMap["start"]): void;
  classify(d: NarratorEventMap["classify"]): void;
  discover(d: NarratorEventMap["discover"]): void;
  sandboxStart(d: NarratorEventMap["sandboxStart"]): void;
  sandboxX402(d: NarratorEventMap["sandboxX402"]): void;
  sandboxResponse(d: NarratorEventMap["sandboxResponse"]): void;
  decision(d: NarratorEventMap["decision"]): void;
  purchaseSigning(d: NarratorEventMap["purchaseSigning"]): void;
  purchaseConfirmed(d: NarratorEventMap["purchaseConfirmed"]): void;
  fetchProgress(bytes: number): void;
  fetchDone(d: NarratorEventMap["fetchDone"]): void;
  verifyHash(d: NarratorEventMap["verifyHash"]): void;
  decompress(d: NarratorEventMap["decompress"]): void;
  executeStart(d: NarratorEventMap["executeStart"]): void;
  executeToken(token: string): void;
  executeDone(d: NarratorEventMap["executeDone"]): void;
  complete(d: NarratorEventMap["complete"]): void;
  warn(msg: string): void;
  error(d: NarratorEventMap["error"]): void;
}
