/**
 * Cross-package types shared by frontend, backend (via codegen), and buyer-agent.
 * The IDL lives in ./idl.ts.
 */

export { AGENTVAULT_IDL } from "./idl.js";
export type { AgentVaultIDL } from "./idl.js";

// ─────────────────────────── Domain types ────────────────────────────

export type SolanaPubkey = string;
export type ArweaveTxId = string;
export type HashHex = string;

export interface Listing {
  /** Listing PDA, base58. */
  id: string;
  address: string;            // alias for id (buyer-agent uses this name)
  seller: SolanaPubkey;
  title: string;
  modelId: string;
  tags: string[];
  /** USDC micro-units (6 decimals). */
  priceUsdc: bigint;
  sandboxPriceUsdc: bigint;
  arweaveTx: ArweaveTxId;
  contentHashHex: HashHex;
  quantSeed: number;
  bitsPerChannel: number;     // 25 | 35 | 40
  seqLen: number;
  active: boolean;
  purchases: number;
  createdAt: string;          // ISO
  /** rough size after compression in MB; not on-chain, derived in indexer. */
  compressedMB: number;
  metadata: {
    seed: number;
    bits: number;
    seq_len: number;
    model_id: string;
  };
}

export interface ListingPreview {
  id: string;
  title: string;
  price: number;
  purchases: number;
}

export interface FeeBreakdown {
  base_usdc: number;
  compute_usdc: number;
  storage_usdc: number;
  total_usdc: number;
  currency: "USDC";
  decimals: 6;
}

export interface SerializedInstruction {
  programId: string;
  keys: Array<{ pubkey: string; isSigner: boolean; isWritable: boolean }>;
  data: string;               // base64
}

export interface AgentRunOptions {
  backendUrl: string;
  workerUrl?: string;
  maxBudgetUsdc: number;      // human USDC, multiplied to micro-units inside
  preferredModelId?: string;
  llm: import("./llm.js").LLMClient;
}

export interface TaskResult {
  status: "success" | "failure";
  task: string;
  reason?: string;
  response?: string;
  memoryUsed?: string;
  totalCostUsdc: number;      // human USDC
  durationMs: number;
  txSignatures: string[];
}

// ─────────────────────────── WebSocket message types ─────────────────

export interface BaseWSMessage<T extends string = string, D = unknown> {
  type: T;
  ts: number;
  data: D;
}

export type UploadMessage =
  | BaseWSMessage<"ws.hello", { channel: string }>
  | BaseWSMessage<"ws.ping", Record<string, never>>
  | BaseWSMessage<"upload.received", { size_bytes: number }>
  | BaseWSMessage<"compress.started", { worker_id: string }>
  | BaseWSMessage<"compress.progress", { percent: number; current_layer: number; total_layers: number }>
  | BaseWSMessage<"compress.done", { compressed_size_bytes: number; ratio: number; content_hash_hex: HashHex }>
  | BaseWSMessage<"arweave.upload.started", Record<string, never>>
  | BaseWSMessage<"arweave.upload.progress", { percent: number; bytes_uploaded: number }>
  | BaseWSMessage<"arweave.upload.done", { arweave_tx: ArweaveTxId }>
  | BaseWSMessage<"listing.pending", { instruction: SerializedInstruction }>
  | BaseWSMessage<"listing.confirmed", { listing_pda: string; tx_signature: string }>
  | BaseWSMessage<"error", { code: string; message: string; recoverable: boolean }>;

export type AgentMessage =
  | BaseWSMessage<"agent.start", { task: string; budget_usdc: number }>
  | BaseWSMessage<"agent.classify", { tags: string[]; reasoning?: string; domain?: string }>
  | BaseWSMessage<"agent.discover", { candidates: ListingPreview[] }>
  | BaseWSMessage<"agent.sandbox.start", { listing_id: string; query: string }>
  | BaseWSMessage<"agent.sandbox.x402", { listing_id: string; tx_signature: string; amount_usdc: number }>
  | BaseWSMessage<"agent.sandbox.response", { listing_id: string; response: string; score: number }>
  | BaseWSMessage<"agent.decision", { winner_id: string; reasoning: string; score: number }>
  | BaseWSMessage<"agent.purchase.signing", { listing_id: string }>
  | BaseWSMessage<"agent.purchase.confirmed", { tx_signature: string; license_pda: string }>
  | BaseWSMessage<"agent.fetch.arweave", { arweave_tx: string; bytes: number }>
  | BaseWSMessage<"agent.verify.hash", { hash_hex: string; verified: boolean }>
  | BaseWSMessage<"agent.decompress", { decompressed_size_mb: number; load_time_ms: number }>
  | BaseWSMessage<"agent.execute.start", { prompt: string }>
  | BaseWSMessage<"agent.execute.token", { token: string }>
  | BaseWSMessage<"agent.execute.done", { output: string; total_tokens: number }>
  | BaseWSMessage<"agent.complete", { total_cost_usdc: number; duration_ms: number }>
  | BaseWSMessage<"agent.warn", { message: string }>
  | BaseWSMessage<"agent.error", { phase: string; error: string }>;

export type ListingMessage =
  | BaseWSMessage<"listing.purchase", { buyer: string; amount_usdc: number; tx: string }>
  | BaseWSMessage<"listing.sandbox", { buyer: string; queries_left: number }>
  | BaseWSMessage<"listing.price_update", { new_price: number; old_price: number }>
  | BaseWSMessage<"listing.delisted", Record<string, never>>;

export type UserMessage =
  | BaseWSMessage<"user.sale", { listing_id: string; amount_usdc: number }>
  | BaseWSMessage<"user.purchase_confirmed", { listing_id: string }>
  | BaseWSMessage<"user.decision_anchored", { decision_pda: string }>;

export type WSMessage = UploadMessage | AgentMessage | ListingMessage | UserMessage;

// ─────────────────────────── REST API DTOs ───────────────────────────

export interface ListingsQuery {
  tags?: string[];
  model?: string;
  minPrice?: number;
  maxPrice?: number;
  seller?: string;
  active?: boolean;
  sort?: "created_at" | "purchases" | "price";
  limit?: number;
  cursor?: string;
}

export interface ListingsPage {
  items: ListingDTO[];
  next_cursor: string | null;
}

/** Wire-format DTO returned by the FastAPI backend (snake_case). */
export interface ListingDTO {
  id: string;
  seller: string;
  title: string;
  model_id: string;
  tags: string[];
  price_usdc: number;
  sandbox_price_usdc: number;
  arweave_tx: string;
  content_hash_hex: string;
  quant_seed: number;
  bits_per_channel: number;
  seq_len: number;
  active: boolean;
  purchases: number;
  created_at: string;
}

export interface UploadInitRequest {
  seller_pubkey: string;
  expected_size_bytes: number;
}

export interface UploadInitResponse {
  upload_id: string;
  fee_breakdown: FeeBreakdown;
  fee_payment_address: string;
  ws_token: string;
  ws_channel: string;
}

export interface UploadFinalizeRequest {
  upload_id: string;
  seller_pubkey: string;
  title: string;
  tags: string[];
  price_usdc: number;
  sandbox_price_usdc: number;
}

export interface UploadFinalizeResponse {
  listing_pda: string;
  instruction: SerializedInstruction;
}

export interface VerifyHashResponse {
  found: boolean;
  kind?: "memory_listing" | "decision_record";
  on_chain_pda?: string;
  arweave_tx?: string;
  anchored_at_slot?: number;
  anchored_at?: string;
}

export interface DecisionDTO {
  id: string;
  agent_id: string;
  decision_type: string;
  context_hash_hex: string;
  arweave_tx: string;
  decision_data_b64: string;
  timestamp: string;
  on_chain_slot: number;
}

// ─────────────────────────── x402 helpers ────────────────────────────

export interface PaymentRequirements {
  scheme: "exact";
  network: string;
  maxAmountRequired: string;
  resource: string;
  description: string;
  mimeType: string;
  payTo: string;
  asset: { address: string };
  maxTimeoutSeconds: number;
}

export interface PaymentRequiredResponse {
  x402Version: 1;
  accepts: PaymentRequirements[];
}

// ─────────────────────────── Backwards-compat aliases ────────────────

export interface MemoryListing extends ListingDTO {}

export interface SandboxQuery {
  listingId: string;
  prompt: string;
}

export interface SandboxResponseDTO {
  listingId: string;
  response: string;
  durationMs: number;
}

export type WSEvent = WSMessage;
