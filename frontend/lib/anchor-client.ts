/**
 * Browser Anchor client. Builds an `AnchorProvider` from the connected wallet
 * + RPC connection and returns a typed `Program`. Used by the buy / list /
 * delist hooks.
 */
import { AnchorProvider, Program, BN } from "@coral-xyz/anchor";
import type { WalletContextState } from "@solana/wallet-adapter-react";
import {
  Connection,
  PublicKey,
  Transaction,
  type TransactionInstruction,
} from "@solana/web3.js";
import {
  getAssociatedTokenAddressSync,
  ASSOCIATED_TOKEN_PROGRAM_ID,
  TOKEN_PROGRAM_ID,
  createAssociatedTokenAccountInstruction,
} from "@solana/spl-token";

import { AGENTVAULT_IDL } from "@agentvault/types";
import { PROGRAM_ID, USDC_MINT, TREASURY } from "./constants";

const PROGRAM_PK = new PublicKey(PROGRAM_ID);
const USDC_MINT_PK = new PublicKey(USDC_MINT);
const TREASURY_PK = new PublicKey(TREASURY);

interface ProviderWallet {
  publicKey: PublicKey;
  signTransaction: <T extends Transaction>(tx: T) => Promise<T>;
  signAllTransactions: <T extends Transaction>(txs: T[]) => Promise<T[]>;
}

function asProviderWallet(wallet: WalletContextState): ProviderWallet {
  if (!wallet.publicKey || !wallet.signTransaction || !wallet.signAllTransactions) {
    throw new Error("Wallet not connected");
  }
  return {
    publicKey: wallet.publicKey,
    signTransaction: wallet.signTransaction as ProviderWallet["signTransaction"],
    signAllTransactions: wallet.signAllTransactions as ProviderWallet["signAllTransactions"],
  };
}

export function getProgram(connection: Connection, wallet: WalletContextState): any {
  const provider = new AnchorProvider(connection, asProviderWallet(wallet) as any, {
    commitment: "confirmed",
    preflightCommitment: "confirmed",
  });
  // The IDL was hand-mirrored from the Rust source; cast through `any` since
  // Anchor typegen-only types diverge between 0.29 IDL shape and 0.30 SDK.
  return new Program(AGENTVAULT_IDL as any, provider);
}

export function findConfigPda(): [PublicKey, number] {
  return PublicKey.findProgramAddressSync([Buffer.from("config")], PROGRAM_PK);
}

export function findListingPda(seller: PublicKey, contentHash: Uint8Array): [PublicKey, number] {
  if (contentHash.length !== 32) throw new Error("contentHash must be 32 bytes");
  return PublicKey.findProgramAddressSync(
    [Buffer.from("listing"), seller.toBuffer(), Buffer.from(contentHash)],
    PROGRAM_PK,
  );
}

export function findLicensePda(buyer: PublicKey, listing: PublicKey): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("license"), buyer.toBuffer(), listing.toBuffer()],
    PROGRAM_PK,
  );
}

export function findSandboxPda(buyer: PublicKey, listing: PublicKey): [PublicKey, number] {
  return PublicKey.findProgramAddressSync(
    [Buffer.from("sandbox"), buyer.toBuffer(), listing.toBuffer()],
    PROGRAM_PK,
  );
}

/**
 * Build a buyMemory tx and send it. Uses ATAs for buyer/seller/treasury and
 * inserts a create-ATA ix for whichever ones don't exist yet (mainnet UX).
 */
export async function buyMemory(opts: {
  connection: Connection;
  wallet: WalletContextState;
  listing: PublicKey;
  seller: PublicKey;
}): Promise<string> {
  const { connection, wallet, listing, seller } = opts;
  const buyer = wallet.publicKey!;
  const program = getProgram(connection, wallet);

  const [config] = findConfigPda();
  const [license] = findLicensePda(buyer, listing);

  const buyerAta = getAssociatedTokenAddressSync(USDC_MINT_PK, buyer);
  const sellerAta = getAssociatedTokenAddressSync(USDC_MINT_PK, seller);
  const treasuryAta = getAssociatedTokenAddressSync(USDC_MINT_PK, TREASURY_PK);

  const preIxs: TransactionInstruction[] = [];
  for (const [owner, ata] of [
    [seller, sellerAta] as const,
    [TREASURY_PK, treasuryAta] as const,
  ]) {
    const info = await connection.getAccountInfo(ata);
    if (!info) {
      preIxs.push(
        createAssociatedTokenAccountInstruction(
          buyer,
          ata,
          owner,
          USDC_MINT_PK,
        ),
      );
    }
  }

  return program.methods
    .buyMemory()
    .accounts({
      buyer,
      config,
      listing,
      license,
      usdcMint: USDC_MINT_PK,
      buyerUsdcAta: buyerAta,
      sellerUsdcAta: sellerAta,
      treasuryUsdcAta: treasuryAta,
      tokenProgram: TOKEN_PROGRAM_ID,
      systemProgram: PublicKey.default,
    })
    .preInstructions(preIxs)
    .rpc();
}

/**
 * Build a listMemory tx with the values resolved by the upload pipeline.
 * The listing PDA is derived from (seller, contentHash) so the caller doesn't
 * need to pass it in.
 */
export async function listMemory(opts: {
  connection: Connection;
  wallet: WalletContextState;
  arweaveTx: string;
  contentHash: Uint8Array;
  modelId: string;
  quantSeed: bigint | number;
  bitsPerChannel: number;
  seqLen: number;
  priceUsdc: bigint | number;
  sandboxPriceUsdc: bigint | number;
  title: string;
  tags: string[];
}): Promise<{ signature: string; listing: PublicKey }> {
  const { connection, wallet, contentHash } = opts;
  const seller = wallet.publicKey!;
  const program = getProgram(connection, wallet);

  const [config] = findConfigPda();
  const [listing] = findListingPda(seller, contentHash);

  const signature = await program.methods
    .listMemory(
      opts.arweaveTx,
      Array.from(contentHash),
      opts.modelId,
      new BN(opts.quantSeed.toString()),
      opts.bitsPerChannel,
      opts.seqLen,
      new BN(opts.priceUsdc.toString()),
      new BN(opts.sandboxPriceUsdc.toString()),
      opts.title,
      opts.tags,
    )
    .accounts({
      seller,
      config,
      listing,
      systemProgram: PublicKey.default,
    })
    .rpc();

  return { signature, listing };
}

export async function delistMemory(opts: {
  connection: Connection;
  wallet: WalletContextState;
  listing: PublicKey;
}): Promise<string> {
  const program = getProgram(opts.connection, opts.wallet);
  return program.methods
    .delistMemory()
    .accounts({
      seller: opts.wallet.publicKey!,
      listing: opts.listing,
    })
    .rpc();
}
