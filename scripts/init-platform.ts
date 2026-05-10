/**
 * One-time bootstrap: invoke initializePlatform on the freshly-deployed
 * program so the [b"config"] PDA exists. We hand-build the instruction
 * (sha256-derived discriminator + Borsh args) to avoid IDL-shape mismatch
 * between Anchor 0.29 IDLs and the 0.30.1 SDK.
 */
import {
  Connection,
  Keypair,
  PublicKey,
  SystemProgram,
  Transaction,
  TransactionInstruction,
} from "@solana/web3.js";
import bs58 from "bs58";
import { createHash } from "node:crypto";
import fs from "node:fs";

const RPC = process.env.SOLANA_RPC_URL ?? "https://api.devnet.solana.com";
const PROGRAM_ID = new PublicKey(
  process.env.AGENTVAULT_PROGRAM_ID ?? "HvWGEDbnRCVThyCNwUVpFRfWsHx2aqT9Ttotr4QovGCF",
);
const USDC_MINT = new PublicKey(
  process.env.USDC_MINT ?? "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
);
const PLATFORM_FEE_BPS = Number(process.env.PLATFORM_FEE_BPS ?? "1000"); // 10%
const KEYPAIR_PATH =
  process.env.WALLET_KEYPAIR ?? `${process.env.HOME}/.config/solana/id.json`;

function loadKeypair(): Keypair {
  const raw = fs.readFileSync(KEYPAIR_PATH, "utf-8").trim();
  if (raw.startsWith("[")) {
    return Keypair.fromSecretKey(Uint8Array.from(JSON.parse(raw)));
  }
  return Keypair.fromSecretKey(bs58.decode(raw));
}

/** Anchor instruction discriminator: first 8 bytes of sha256("global:<snake_name>"). */
function ixDisc(name: string): Buffer {
  return createHash("sha256").update(`global:${name}`).digest().subarray(0, 8);
}

async function main() {
  const conn = new Connection(RPC, "confirmed");
  const wallet = loadKeypair();
  const treasury = new PublicKey(
    process.env.PLATFORM_TREASURY ?? wallet.publicKey.toBase58(),
  );

  const [config] = PublicKey.findProgramAddressSync(
    [Buffer.from("config")],
    PROGRAM_ID,
  );

  const existing = await conn.getAccountInfo(config);
  if (existing) {
    console.log(`config PDA ${config.toBase58()} already initialised`);
    return;
  }

  console.log(`initializing platform...`);
  console.log(`  authority : ${wallet.publicKey.toBase58()}`);
  console.log(`  treasury  : ${treasury.toBase58()}`);
  console.log(`  usdc_mint : ${USDC_MINT.toBase58()}`);
  console.log(`  fee_bps   : ${PLATFORM_FEE_BPS}`);

  // Args: treasury (Pubkey 32) || usdc_mint (Pubkey 32) || fee_bps (u16 LE).
  const data = Buffer.concat([
    ixDisc("initialize_platform"),
    treasury.toBuffer(),
    USDC_MINT.toBuffer(),
    Buffer.from(Uint16Array.of(PLATFORM_FEE_BPS).buffer),
  ]);

  const ix = new TransactionInstruction({
    programId: PROGRAM_ID,
    keys: [
      { pubkey: wallet.publicKey, isSigner: true, isWritable: true },
      { pubkey: config, isSigner: false, isWritable: true },
      { pubkey: SystemProgram.programId, isSigner: false, isWritable: false },
    ],
    data,
  });

  const { blockhash, lastValidBlockHeight } = await conn.getLatestBlockhash("confirmed");
  const tx = new Transaction({ feePayer: wallet.publicKey, blockhash, lastValidBlockHeight }).add(ix);
  tx.sign(wallet);
  const sig = await conn.sendRawTransaction(tx.serialize(), { skipPreflight: false });
  await conn.confirmTransaction({ signature: sig, blockhash, lastValidBlockHeight }, "confirmed");

  console.log(`config PDA: ${config.toBase58()}`);
  console.log(`tx: ${sig}`);
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
