#!/usr/bin/env node
/**
 * Tiny Node sidecar that wraps @irys/sdk so the Python backend can upload
 * blobs to Arweave without ever loading the Bundlr keypair into a long-lived
 * web worker.
 *
 *  POST /upload   { blob: base64, tags?: [{name, value}] }  -> { arweave_tx }
 *  GET  /balance                                            -> { balance, atomic }
 *  GET  /healthz                                            -> { ok: true }
 *
 * Env:
 *   IRYS_NETWORK     "devnet" | "mainnet"          (default "devnet")
 *   IRYS_TOKEN       "solana"                       (default "solana")
 *   IRYS_KEYPAIR     base58 secret key (64 bytes)   REQUIRED
 *   IRYS_SIDECAR_PORT  default 9100
 *   IRYS_RPC_URL     Solana RPC the funder uses
 *
 * Start with:
 *   node scripts/irys-sidecar.js
 */
import http from "node:http";

const PORT = Number(process.env.IRYS_SIDECAR_PORT || 9100);
const NETWORK = process.env.IRYS_NETWORK || "devnet";
const TOKEN = process.env.IRYS_TOKEN || "solana";
const RPC_URL = process.env.IRYS_RPC_URL || "https://api.devnet.solana.com";
const KEYPAIR = process.env.IRYS_KEYPAIR;

if (!KEYPAIR) {
  console.error("[irys-sidecar] IRYS_KEYPAIR env is required (base58 secret)");
  process.exit(1);
}

let irysPromise;
async function getIrys() {
  if (!irysPromise) {
    irysPromise = (async () => {
      // Lazy-import so a missing dep only fails when the sidecar actually runs.
      const { default: Irys } = await import("@irys/sdk");
      const url =
        NETWORK === "mainnet" ? "https://node1.irys.xyz" : "https://devnet.irys.xyz";
      const client = new Irys({
        url,
        token: TOKEN,
        key: KEYPAIR,
        config: { providerUrl: RPC_URL },
      });
      await client.ready();
      return client;
    })();
  }
  return irysPromise;
}

async function readJsonBody(req) {
  return await new Promise((resolve, reject) => {
    const chunks = [];
    req.on("data", (c) => chunks.push(c));
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf-8") || "{}"));
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

function send(res, status, body) {
  res.writeHead(status, { "Content-Type": "application/json" });
  res.end(JSON.stringify(body));
}

async function handleUpload(req, res) {
  const body = await readJsonBody(req);
  if (!body.blob) return send(res, 400, { error: "missing blob (base64)" });
  const buf = Buffer.from(body.blob, "base64");
  const irys = await getIrys();

  // Pre-fund check — Irys nodes reject uploads paid out of an empty balance.
  const price = await irys.getPrice(buf.length);
  const balance = await irys.getLoadedBalance();
  if (balance.lt(price)) {
    const need = price.minus(balance);
    try {
      await irys.fund(need);
    } catch (e) {
      return send(res, 402, {
        error: `insufficient balance and fund() failed: ${e?.message ?? e}`,
        need_atomic: need.toString(),
      });
    }
  }

  const tags = (body.tags || []).map((t) => ({ name: String(t.name), value: String(t.value) }));
  const receipt = await irys.upload(buf, { tags });
  return send(res, 200, { arweave_tx: receipt.id });
}

async function handleBalance(_req, res) {
  const irys = await getIrys();
  const atomic = await irys.getLoadedBalance();
  const balance = irys.utils.fromAtomic(atomic).toString();
  return send(res, 200, { balance, atomic: atomic.toString() });
}

const server = http.createServer(async (req, res) => {
  try {
    if (req.method === "GET" && req.url === "/healthz") return send(res, 200, { ok: true });
    if (req.method === "GET" && req.url === "/balance") return handleBalance(req, res);
    if (req.method === "POST" && req.url === "/upload") return handleUpload(req, res);
    return send(res, 404, { error: "not found" });
  } catch (e) {
    console.error("[irys-sidecar] error:", e);
    return send(res, 500, { error: e?.message ?? String(e) });
  }
});

server.listen(PORT, () => {
  console.log(
    `[irys-sidecar] listening on :${PORT} (network=${NETWORK} token=${TOKEN} rpc=${RPC_URL})`,
  );
});
