import {
  Connection,
  Keypair,
  PublicKey,
  Transaction,
} from "@solana/web3.js";
import {
  createTransferCheckedInstruction,
  getAssociatedTokenAddressSync,
  getAccount,
} from "@solana/spl-token";
import bs58 from "bs58";

import { config } from "../config.js";

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

interface X402Requirements {
  /**
   * Subset of the x402 spec we actually use:
   * https://github.com/coinbase/x402
   */
  scheme: string; // "exact"
  network: string; // "solana-devnet" / "solana"
  asset: string; // USDC mint pubkey
  payTo: string; // recipient (seller) ATA owner
  amount: string; // micro-USDC (6 decimals)
  decimals?: number; // defaults to 6
  resource?: string;
  description?: string;
}

/**
 * x402 client that builds + signs a real USDC SPL transfer when a 402 lands
 * with x402 requirements. We support the "exact" scheme on Solana — enough
 * for sandbox queries and any other gated POST.
 */
export class X402Client {
  constructor(public connection: Connection, public wallet: Keypair) {}

  async fetch(params: X402FetchParams): Promise<X402FetchResult> {
    const init: RequestInit = {
      method: params.method ?? "POST",
      headers: { "Content-Type": "application/json" },
      body: params.body ? JSON.stringify(params.body) : undefined,
    };
    const r = await fetch(params.url, init);

    if (r.status !== 402) {
      if (!r.ok) {
        throw new Error(`x402 fetch failed: ${r.status} ${await r.text()}`);
      }
      return await this._readResult(r);
    }

    // 402 path — parse requirements, build & sign payment, retry with header.
    const reqsRaw = await r.text();
    const requirements = parseRequirements(reqsRaw);
    const paymentHeader = await this._signPayment(requirements);

    const paid = await fetch(params.url, {
      ...init,
      headers: {
        ...(init.headers as Record<string, string>),
        "X-PAYMENT": paymentHeader,
      },
    });
    if (!paid.ok) {
      throw new Error(`x402 retry failed: ${paid.status} ${await paid.text()}`);
    }
    return await this._readResult(paid);
  }

  private async _readResult(r: Response): Promise<X402FetchResult> {
    const data = (await r.json()) as {
      response: string;
      tx_signature?: string;
      txSignature?: string;
      queries_remaining?: number;
      queriesRemaining?: number;
    };
    return {
      response: data.response,
      txSignature: data.tx_signature ?? data.txSignature ?? "",
      queriesRemaining: data.queries_remaining ?? data.queriesRemaining,
    };
  }

  private async _signPayment(req: X402Requirements): Promise<string> {
    if (req.scheme !== "exact") {
      throw new Error(`unsupported x402 scheme: ${req.scheme}`);
    }
    const network = req.network.toLowerCase();
    if (!network.startsWith("solana")) {
      throw new Error(`unsupported x402 network: ${req.network}`);
    }

    const mint = new PublicKey(req.asset);
    const recipientOwner = new PublicKey(req.payTo);
    const amountRaw = BigInt(req.amount);
    const decimals = req.decimals ?? 6;

    const buyerAta = getAssociatedTokenAddressSync(mint, this.wallet.publicKey);
    const sellerAta = getAssociatedTokenAddressSync(mint, recipientOwner);

    // Best-effort balance check so we fail fast with a useful error rather
    // than a generic "insufficient funds" deep in tx simulation.
    try {
      const balance = await getAccount(this.connection, buyerAta);
      if (balance.amount < amountRaw) {
        throw new Error(
          `insufficient USDC: ata=${buyerAta.toBase58()} has ${balance.amount}, need ${amountRaw}`,
        );
      }
    } catch (e: any) {
      if (!e?.message?.includes("insufficient USDC")) {
        // Account doesn't exist yet → real ATA setup hasn't happened. Surface
        // a clear error instead of letting the tx fail later.
        throw new Error(
          `buyer USDC ATA missing for ${this.wallet.publicKey.toBase58()} (${buyerAta.toBase58()}). Fund + ATA-init the wallet first.`,
        );
      }
      throw e;
    }

    const ix = createTransferCheckedInstruction(
      buyerAta,
      mint,
      sellerAta,
      this.wallet.publicKey,
      amountRaw,
      decimals,
    );

    const { blockhash, lastValidBlockHeight } =
      await this.connection.getLatestBlockhash("confirmed");
    const tx = new Transaction({
      feePayer: this.wallet.publicKey,
      blockhash,
      lastValidBlockHeight,
    }).add(ix);
    tx.sign(this.wallet);

    // x402 expects the signed tx serialized and base64-encoded inside a
    // structured payload. Keep it minimal — payer + signed tx only.
    const signed = tx.serialize();
    const payload = {
      x402Version: 1,
      scheme: "exact",
      network: req.network,
      payload: {
        from: this.wallet.publicKey.toBase58(),
        to: recipientOwner.toBase58(),
        asset: req.asset,
        amount: req.amount,
        signedTransaction: Buffer.from(signed).toString("base64"),
        signedTransactionBase58: bs58.encode(signed),
      },
    };
    return Buffer.from(JSON.stringify(payload)).toString("base64");
  }
}

function parseRequirements(raw: string): X402Requirements {
  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`x402: 402 body is not JSON: ${raw.slice(0, 200)}`);
  }
  // Two common envelope shapes — either the requirements directly, or a
  // top-level `accepts: [...]` list (matches the x402 reference spec).
  const reqs = Array.isArray(parsed.accepts)
    ? parsed.accepts[0]
    : parsed;
  if (!reqs?.scheme || !reqs?.network || !reqs?.asset || !reqs?.payTo || !reqs?.amount) {
    throw new Error(`x402: missing required fields in 402 body: ${raw.slice(0, 200)}`);
  }
  // Default mint to the configured USDC mint when caller leaves it blank.
  if (!reqs.asset) reqs.asset = config.usdcMint;
  return reqs as X402Requirements;
}
