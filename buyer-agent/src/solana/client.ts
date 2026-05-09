import { Connection, Keypair, PublicKey } from "@solana/web3.js";
import { TOKEN_PROGRAM_ID, getAssociatedTokenAddress } from "@solana/spl-token";
import { AnchorProvider, Program, BN } from "@coral-xyz/anchor";
import { AGENTVAULT_IDL } from "@agentvault/types";

import type { Listing } from "../types.js";
import { config } from "../config.js";
import { findConfigPda, findLicensePda } from "./pdas.js";

export class AgentVaultClient {
  program: any;
  provider: AnchorProvider;
  programId: PublicKey;

  constructor(public connection: Connection, public wallet: Keypair) {
    const anchorWallet = {
      publicKey: wallet.publicKey,
      signTransaction: async (tx: any) => {
        tx.partialSign(wallet);
        return tx;
      },
      signAllTransactions: async (txs: any[]) => {
        txs.forEach((tx) => tx.partialSign(wallet));
        return txs;
      },
    } as any;
    this.provider = new AnchorProvider(connection, anchorWallet, {
      commitment: "confirmed",
    });
    this.programId = new PublicKey(config.programId);
    this.program = new (Program as any)(AGENTVAULT_IDL, this.provider);
  }

  /** Discovery is delegated to the backend's indexed mirror — much faster
   * than scanning getProgramAccounts and gives us tag-filter support. */
  async findListings(filters: {
    tags?: string[];
    modelId?: string;
    activeOnly?: boolean;
    limit?: number;
  }): Promise<Listing[]> {
    const url = new URL(`${config.backendUrl}/v1/listings`);
    if (filters.tags?.length) url.searchParams.set("tags", filters.tags.join(","));
    if (filters.modelId) url.searchParams.set("model", filters.modelId);
    if (filters.activeOnly) url.searchParams.set("active", "true");
    if (filters.limit) url.searchParams.set("limit", String(filters.limit));

    const r = await fetch(url.toString());
    if (!r.ok) {
      // Hackathon-mode fallback: empty list if backend isn't reachable.
      return [];
    }
    const data = (await r.json()) as { items?: any[] };
    return (data.items ?? []).map(this.parseListing);
  }

  async buyMemory(
    listingAddress: string,
  ): Promise<{ txSignature: string; licensePda: string }> {
    const listing = new PublicKey(listingAddress);
    const buyer = this.provider.wallet.publicKey;
    const usdcMint = new PublicKey(config.usdcMint);

    const [licensePda] = findLicensePda(buyer, listing, this.programId);
    const [configPda] = findConfigPda(this.programId);

    const buyerAta = await getAssociatedTokenAddress(usdcMint, buyer);
    const listingAccount = await this.program.account.memoryListing.fetch(listing);
    const sellerAta = await getAssociatedTokenAddress(usdcMint, listingAccount.seller);
    const treasuryAta = await getAssociatedTokenAddress(
      usdcMint,
      new PublicKey(config.treasury),
    );

    const txSig = await this.program.methods
      .buyMemory()
      .accounts({
        buyer,
        config: configPda,
        listing,
        license: licensePda,
        usdcMint,
        buyerUsdcAta: buyerAta,
        sellerUsdcAta: sellerAta,
        treasuryUsdcAta: treasuryAta,
        tokenProgram: TOKEN_PROGRAM_ID,
        systemProgram: PublicKey.default,
      })
      .rpc();

    return { txSignature: txSig, licensePda: licensePda.toBase58() };
  }

  private parseListing = (raw: any): Listing => {
    const seqLen = Number(raw.seq_len);
    return {
      id: raw.id,
      address: raw.id,
      seller: raw.seller,
      title: raw.title,
      modelId: raw.model_id,
      tags: raw.tags ?? [],
      priceUsdc: BigInt(raw.price_usdc),
      sandboxPriceUsdc: BigInt(raw.sandbox_price_usdc),
      arweaveTx: raw.arweave_tx,
      contentHashHex: raw.content_hash_hex,
      quantSeed: Number(raw.quant_seed),
      bitsPerChannel: Number(raw.bits_per_channel),
      seqLen,
      active: Boolean(raw.active),
      purchases: Number(raw.purchases),
      createdAt: raw.created_at,
      compressedMB: seqLen * 0.05,
      metadata: {
        seed: Number(raw.quant_seed),
        bits: Number(raw.bits_per_channel) / 10,
        seq_len: seqLen,
        model_id: raw.model_id,
      },
    };
  };
}

// Export BN to avoid unused import noise when testing this module standalone.
export { BN };
