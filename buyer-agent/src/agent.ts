import { Connection, Keypair } from "@solana/web3.js";
import bs58 from "bs58";

import { config } from "./config.js";

/**
 * Decode an agent wallet from one of:
 *  - base58 secret key (87-char Phantom-style export)
 *  - JSON array of 64 ints (Solana CLI keypair file contents)
 * Throws if the value can't be parsed — we'd rather fail loudly than silently
 * fall back to a throwaway wallet that has no USDC.
 */
function loadKeypair(raw: string): Keypair {
  const trimmed = raw.trim();
  if (trimmed.startsWith("[")) {
    const arr = JSON.parse(trimmed) as number[];
    if (arr.length !== 64) {
      throw new Error(`AGENT_KEYPAIR JSON array must be 64 bytes, got ${arr.length}`);
    }
    return Keypair.fromSecretKey(Uint8Array.from(arr));
  }
  const bytes = bs58.decode(trimmed);
  if (bytes.length !== 64) {
    throw new Error(`AGENT_KEYPAIR base58 must decode to 64 bytes, got ${bytes.length}`);
  }
  return Keypair.fromSecretKey(bytes);
}
import { AgentVaultClient } from "./solana/client.js";
import { X402Client } from "./x402/client.js";
import { WorkerClient } from "./runtime/worker_client.js";
import { fetchFromArweave } from "./arweave/fetcher.js";
import { sha256, hexEqual } from "./util/crypto.js";
import { classifyTask } from "./reasoning/classifier.js";
import { generateProbe } from "./reasoning/probe_generator.js";
import { evaluateResponse } from "./reasoning/evaluator.js";
import { pickWinner, ScoredCandidate } from "./reasoning/decision.js";
import type { Narrator, AgentRunOptions, TaskResult, Listing } from "./types.js";

export class MemoryShoppingAgent {
  constructor(
    private opts: AgentRunOptions,
    private narrator: Narrator,
    private avc: AgentVaultClient,
    private x402: X402Client,
    private worker: WorkerClient,
  ) {}

  async run(task: string): Promise<TaskResult> {
    const startedAt = Date.now();
    const txSignatures: string[] = [];
    let totalCostUsdcMicro = 0;

    this.narrator.start({ task, budget_usdc: this.opts.maxBudgetUsdc });

    try {
      // 1. CLASSIFY
      const classified = await classifyTask(task, this.opts.llm);
      this.narrator.classify(classified);

      // 2. DISCOVER
      const candidates = await this.avc.findListings({
        tags: classified.tags,
        modelId: this.opts.preferredModelId,
        activeOnly: true,
        limit: 5,
      });
      this.narrator.discover(candidates);
      if (candidates.length === 0) {
        return this.fail(task, "no_candidates", startedAt, txSignatures, totalCostUsdcMicro);
      }

      // 3. EVALUATE
      const probe = await generateProbe(task, classified.tags, this.opts.llm);
      const top = candidates.slice(0, 3);
      const scored: ScoredCandidate[] = [];

      for (const listing of top) {
        try {
          this.narrator.sandboxStart({ listing_id: listing.address, query: probe });
          const result = await this.x402.fetch({
            url: `${this.opts.backendUrl}/v1/sandbox/${listing.address}`,
            method: "POST",
            body: { query: probe },
          });
          this.narrator.sandboxX402({
            listing_id: listing.address,
            tx_signature: result.txSignature ?? "",
            amount_usdc: Number(listing.sandboxPriceUsdc),
          });
          totalCostUsdcMicro += Number(listing.sandboxPriceUsdc);
          if (result.txSignature) txSignatures.push(result.txSignature);

          const score = await evaluateResponse({
            task,
            probe,
            response: result.response,
            llm: this.opts.llm,
          });
          this.narrator.sandboxResponse({
            listing_id: listing.address,
            response: result.response,
            score,
          });
          scored.push({ listing, score, response: result.response, tx: result.txSignature ?? "" });
        } catch (e: any) {
          this.narrator.warn(`sandbox failed for ${listing.title}: ${e.message}`);
        }
      }

      if (scored.length === 0) {
        return this.fail(task, "all_sandboxes_failed", startedAt, txSignatures, totalCostUsdcMicro);
      }

      // 4. DECIDE
      const winner = pickWinner(scored, {
        maxBudgetUsdc: this.opts.maxBudgetUsdc * 1_000_000 - totalCostUsdcMicro,
      });
      if (!winner) {
        return this.fail(task, "over_budget", startedAt, txSignatures, totalCostUsdcMicro);
      }
      this.narrator.decision({
        winner_id: winner.listing.address,
        reasoning: `score ${winner.score.toFixed(2)} at ${(Number(winner.listing.priceUsdc) / 1e6).toFixed(2)} USDC`,
        score: winner.score,
      });

      // 5. PURCHASE
      this.narrator.purchaseSigning({ listing_id: winner.listing.address });
      const purchase = await this.avc.buyMemory(winner.listing.address);
      txSignatures.push(purchase.txSignature);
      totalCostUsdcMicro += Number(winner.listing.priceUsdc);
      this.narrator.purchaseConfirmed({
        tx_signature: purchase.txSignature,
        license_pda: purchase.licensePda,
      });

      // 6. FETCH
      const blob = await fetchFromArweave(winner.listing.arweaveTx, (b) =>
        this.narrator.fetchProgress(b),
      );
      this.narrator.fetchDone({
        arweave_tx: winner.listing.arweaveTx,
        bytes: blob.length,
      });

      const actualHashHex = sha256(blob);
      const verified = hexEqual(actualHashHex, winner.listing.contentHashHex);
      this.narrator.verifyHash({ hash_hex: actualHashHex, verified });
      if (!verified) {
        throw new Error(
          `hash mismatch — expected ${winner.listing.contentHashHex}, got ${actualHashHex}`,
        );
      }

      // 7. LOAD
      const loadStart = Date.now();
      const cacheId = await this.worker.decompressAndLoad({
        blob,
        metadata: winner.listing.metadata,
        modelId: winner.listing.modelId,
      });
      this.narrator.decompress({
        decompressed_size_mb: this.estimateDecompressedMB(blob.length, winner.listing),
        load_time_ms: Date.now() - loadStart,
      });

      // 8. EXECUTE
      this.narrator.executeStart({ prompt: task });
      const tokens: string[] = [];
      const output = await this.worker.inferenceStream({
        cache_id: cacheId,
        prompt: task,
        max_tokens: 500,
        on_token: (tok) => {
          tokens.push(tok);
          this.narrator.executeToken(tok);
        },
      });
      this.narrator.executeDone({ output, total_tokens: tokens.length });

      const durationMs = Date.now() - startedAt;
      this.narrator.complete({
        total_cost_usdc: totalCostUsdcMicro / 1_000_000,
        duration_ms: durationMs,
      });

      return {
        status: "success",
        task,
        response: output,
        memoryUsed: winner.listing.title,
        totalCostUsdc: totalCostUsdcMicro / 1_000_000,
        durationMs,
        txSignatures,
      };
    } catch (e: any) {
      this.narrator.error({ phase: "unknown", error: e?.message ?? String(e) });
      return this.fail(task, e?.message ?? "unknown", startedAt, txSignatures, totalCostUsdcMicro);
    }
  }

  private fail(
    task: string,
    reason: string,
    startedAt: number,
    txSigs: string[],
    costMicro: number,
  ): TaskResult {
    return {
      status: "failure",
      task,
      reason,
      durationMs: Date.now() - startedAt,
      txSignatures: txSigs,
      totalCostUsdc: costMicro / 1_000_000,
    };
  }

  private estimateDecompressedMB(compressedBytes: number, _listing: Listing): number {
    return (compressedBytes * 4.5) / (1024 * 1024);
  }
}

/** Helper: build a fully-wired agent for the demo. */
export function buildAgent(
  narrator: Narrator,
  opts?: Partial<AgentRunOptions>,
): MemoryShoppingAgent {
  const connection = new Connection(config.solanaRpcUrl, "confirmed");
  let wallet: Keypair;
  if (config.agentKeypairBase58) {
    wallet = loadKeypair(config.agentKeypairBase58);
  } else {
    wallet = Keypair.generate();
    console.warn(
      `[buyer-agent] no AGENT_KEYPAIR set — generated throwaway wallet ${wallet.publicKey.toBase58()}; this wallet has no USDC and cannot pay.`,
    );
  }

  const avc = new AgentVaultClient(connection, wallet);
  const x402 = new X402Client(connection, wallet);
  const worker = new WorkerClient(config.workerUrl, config.workerApiKey);

  const llm = opts?.llm ?? require("./reasoning/llm_client.js").createAnthropicClient(
    config.llm.apiKey,
    config.llm.model,
  );

  return new MemoryShoppingAgent(
    {
      backendUrl: opts?.backendUrl ?? config.backendUrl,
      maxBudgetUsdc: opts?.maxBudgetUsdc ?? config.maxBudgetUsdc,
      preferredModelId: opts?.preferredModelId ?? "qwen2.5-7b-instruct",
      llm,
    },
    narrator,
    avc,
    x402,
    worker,
  );
}
