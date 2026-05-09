import { USDC_DECIMALS } from "./constants";

export function formatUsdc(microUnits: bigint | number, opts: { sign?: boolean } = {}): string {
  const n = typeof microUnits === "bigint" ? Number(microUnits) : microUnits;
  const value = n / 10 ** USDC_DECIMALS;
  const sign = opts.sign && value > 0 ? "+" : "";
  return `${sign}$${value.toFixed(2)}`;
}

export function truncatePubkey(pk: string, head = 4, tail = 4): string {
  if (!pk) return "";
  if (pk.length <= head + tail + 1) return pk;
  return `${pk.slice(0, head)}…${pk.slice(-tail)}`;
}

export function truncateHash(hex: string, head = 6, tail = 6): string {
  if (!hex) return "";
  if (hex.length <= head + tail + 1) return hex;
  return `${hex.slice(0, head)}…${hex.slice(-tail)}`;
}

export function formatRelativeTime(iso: string | Date): string {
  const d = typeof iso === "string" ? new Date(iso) : iso;
  const diffSecs = Math.round((Date.now() - d.getTime()) / 1000);
  const abs = Math.abs(diffSecs);
  if (abs < 60) return `${diffSecs}s ago`;
  if (abs < 3600) return `${Math.round(diffSecs / 60)}m ago`;
  if (abs < 86400) return `${Math.round(diffSecs / 3600)}h ago`;
  return `${Math.round(diffSecs / 86400)}d ago`;
}

export function explorerTxUrl(sig: string, cluster = "devnet"): string {
  return `https://explorer.solana.com/tx/${sig}?cluster=${cluster}`;
}

export function explorerAddressUrl(addr: string, cluster = "devnet"): string {
  return `https://explorer.solana.com/address/${addr}?cluster=${cluster}`;
}

export function arweaveUrl(tx: string): string {
  return `https://arweave.net/${tx}`;
}
