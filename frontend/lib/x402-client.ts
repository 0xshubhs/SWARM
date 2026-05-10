/**
 * Browser-side x402 client. Builds + signs a real USDC SPL transfer with the
 * connected wallet on a 402 response, then retries with `X-PAYMENT`. Mirrors
 * `buyer-agent/src/x402/client.ts` so seller-side facilitator code can treat
 * either origin identically.
 */
import type { WalletContextState } from "@solana/wallet-adapter-react";
import {
  Connection,
  PublicKey,
  Transaction,
} from "@solana/web3.js";
import {
  createTransferCheckedInstruction,
  getAssociatedTokenAddressSync,
} from "@solana/spl-token";
import bs58 from "bs58";

interface X402PayParams {
  url: string;
  body?: unknown;
  wallet: WalletContextState;
  connection: Connection;
  method?: "POST" | "GET";
}

interface X402Requirements {
  scheme: string;
  network: string;
  asset: string;
  payTo: string;
  amount: string;
  decimals?: number;
  resource?: string;
  description?: string;
}

export async function x402Pay({
  url,
  body,
  wallet,
  connection,
  method = "POST",
}: X402PayParams): Promise<Response> {
  if (!wallet.publicKey || !wallet.signTransaction) {
    throw new Error("Wallet not connected");
  }

  const init: RequestInit = {
    method,
    headers: { "Content-Type": "application/json" },
    body: body ? JSON.stringify(body) : undefined,
  };
  const res = await fetch(url, init);
  if (res.status !== 402) return res;

  const reqs = parseRequirements(await res.text());
  const paymentHeader = await signPayment(reqs, wallet, connection);

  return fetch(url, {
    ...init,
    headers: {
      ...(init.headers as Record<string, string>),
      "X-PAYMENT": paymentHeader,
    },
  });
}

async function signPayment(
  req: X402Requirements,
  wallet: WalletContextState,
  connection: Connection,
): Promise<string> {
  if (req.scheme !== "exact") {
    throw new Error(`unsupported x402 scheme: ${req.scheme}`);
  }
  if (!req.network.toLowerCase().startsWith("solana")) {
    throw new Error(`unsupported x402 network: ${req.network}`);
  }

  const buyerPubkey = wallet.publicKey!;
  const mint = new PublicKey(req.asset);
  const recipientOwner = new PublicKey(req.payTo);
  const decimals = req.decimals ?? 6;
  const amount = BigInt(req.amount);

  const buyerAta = getAssociatedTokenAddressSync(mint, buyerPubkey);
  const sellerAta = getAssociatedTokenAddressSync(mint, recipientOwner);

  const ix = createTransferCheckedInstruction(
    buyerAta,
    mint,
    sellerAta,
    buyerPubkey,
    amount,
    decimals,
  );

  const { blockhash, lastValidBlockHeight } = await connection.getLatestBlockhash("confirmed");
  const tx = new Transaction({
    feePayer: buyerPubkey,
    blockhash,
    lastValidBlockHeight,
  }).add(ix);

  const signed = await wallet.signTransaction!(tx);
  const serialized = signed.serialize();

  const payload = {
    x402Version: 1,
    scheme: "exact",
    network: req.network,
    payload: {
      from: buyerPubkey.toBase58(),
      to: recipientOwner.toBase58(),
      asset: req.asset,
      amount: req.amount,
      signedTransaction: bufferToBase64(serialized),
      signedTransactionBase58: bs58.encode(serialized),
    },
  };
  return bufferToBase64(new TextEncoder().encode(JSON.stringify(payload)));
}

function parseRequirements(raw: string): X402Requirements {
  let parsed: any;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new Error(`x402: 402 body is not JSON: ${raw.slice(0, 200)}`);
  }
  const reqs = Array.isArray(parsed.accepts) ? parsed.accepts[0] : parsed;
  if (!reqs?.scheme || !reqs?.network || !reqs?.asset || !reqs?.payTo || !reqs?.amount) {
    throw new Error(`x402: missing required fields in 402 body`);
  }
  return reqs as X402Requirements;
}

function bufferToBase64(buf: Uint8Array): string {
  let binary = "";
  for (let i = 0; i < buf.byteLength; i++) {
    binary += String.fromCharCode(buf[i]!);
  }
  return btoa(binary);
}
