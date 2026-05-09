import type { Narrator } from "../types.js";

const COLOR = {
  reset: "\x1b[0m",
  dim: "\x1b[2m",
  cyan: "\x1b[36m",
  green: "\x1b[32m",
  red: "\x1b[31m",
  yellow: "\x1b[33m",
  magenta: "\x1b[35m",
};

function box(text: string): string {
  const lines = text.split("\n");
  const w = Math.max(...lines.map((l) => l.length));
  const top = "╭" + "─".repeat(w + 2) + "╮";
  const bot = "╰" + "─".repeat(w + 2) + "╯";
  const body = lines.map((l) => "│ " + l.padEnd(w) + " │").join("\n");
  return `${top}\n${body}\n${bot}`;
}

export function createStdoutNarrator(): Narrator {
  return {
    start({ task, budget_usdc }) {
      console.log("\n" + COLOR.cyan + box("Memory Shopping Agent") + COLOR.reset);
      console.log(`${COLOR.yellow}Task:${COLOR.reset} ${task}`);
      console.log(`${COLOR.dim}Budget: $${budget_usdc} USDC${COLOR.reset}\n`);
    },
    classify({ tags, domain }) {
      console.log(`${COLOR.green}→${COLOR.reset} Classified`);
      if (domain) console.log(`${COLOR.dim}    domain: ${domain}${COLOR.reset}`);
      console.log(`${COLOR.dim}    tags:   [${tags.join(", ")}]${COLOR.reset}\n`);
    },
    discover(candidates) {
      console.log(`${COLOR.green}→${COLOR.reset} Found ${candidates.length} candidates`);
      candidates.forEach((c, i) => {
        const price = (Number(c.priceUsdc) / 1e6).toFixed(2).padStart(6);
        console.log(
          `${COLOR.dim}    ${(i + 1).toString().padEnd(2)}. ${c.title.padEnd(40)} $${price} • ${c.purchases} sold${COLOR.reset}`,
        );
      });
      console.log();
    },
    sandboxStart({ listing_id }) {
      process.stdout.write(`${COLOR.dim}    sandbox ${listing_id.slice(0, 8)}…${COLOR.reset}`);
    },
    sandboxX402({ tx_signature, amount_usdc }) {
      process.stdout.write(
        `\r${COLOR.magenta}    💸${COLOR.reset} ${COLOR.dim}x402 paid $${(amount_usdc / 1e6).toFixed(3)} → tx ${tx_signature.slice(0, 8)}…${COLOR.reset}\n`,
      );
    },
    sandboxResponse({ score }) {
      const filled = Math.round(score * 10);
      const bar = "█".repeat(filled) + "░".repeat(10 - filled);
      console.log(`${COLOR.dim}    score: ${bar} ${score.toFixed(2)}${COLOR.reset}`);
    },
    decision({ winner_id, reasoning }) {
      console.log(`\n${COLOR.green}→${COLOR.reset} Decision`);
      console.log(`${COLOR.dim}    winner: ${winner_id.slice(0, 12)}…${COLOR.reset}`);
      console.log(`${COLOR.dim}    ${reasoning}${COLOR.reset}\n`);
    },
    purchaseSigning() {
      process.stdout.write(`${COLOR.dim}    signing buy_memory…${COLOR.reset}`);
    },
    purchaseConfirmed({ tx_signature, license_pda }) {
      process.stdout.write("\r");
      console.log(`${COLOR.green}→${COLOR.reset} Purchased`);
      console.log(
        `${COLOR.magenta}    🔗 https://explorer.solana.com/tx/${tx_signature}?cluster=devnet${COLOR.reset}`,
      );
      console.log(`${COLOR.dim}    license: ${license_pda.slice(0, 12)}…${COLOR.reset}\n`);
    },
    fetchProgress() {
      /* throttled silently */
    },
    fetchDone({ arweave_tx, bytes }) {
      console.log(
        `${COLOR.green}→${COLOR.reset} Downloaded ${(bytes / 1024 / 1024).toFixed(1)} MB from Arweave`,
      );
      console.log(`${COLOR.dim}    https://arweave.net/${arweave_tx}${COLOR.reset}\n`);
    },
    verifyHash({ hash_hex, verified }) {
      if (verified) {
        console.log(
          `${COLOR.green}→${COLOR.reset} ✓ Hash verified ${COLOR.dim}${hash_hex.slice(0, 16)}…${COLOR.reset}\n`,
        );
      } else {
        console.log(`${COLOR.red}→ ✗ Hash MISMATCH — possible tampering!${COLOR.reset}\n`);
      }
    },
    decompress({ decompressed_size_mb, load_time_ms }) {
      console.log(
        `${COLOR.green}→${COLOR.reset} Decompressed (~${decompressed_size_mb.toFixed(0)} MB) loaded in ${load_time_ms}ms\n`,
      );
    },
    executeStart() {
      console.log(`${COLOR.green}→${COLOR.reset} Executing with loaded memory:\n`);
      process.stdout.write(`${COLOR.cyan}  `);
    },
    executeToken(token) {
      process.stdout.write(token);
    },
    executeDone() {
      process.stdout.write(`${COLOR.reset}\n\n`);
    },
    complete({ total_cost_usdc, duration_ms }) {
      console.log(
        COLOR.green +
          box(
            `✓ Task complete\n\nCost: $${total_cost_usdc.toFixed(3)} USDC\nDuration: ${(duration_ms / 1000).toFixed(1)}s`,
          ) +
          COLOR.reset,
      );
    },
    warn(msg) {
      console.log(`${COLOR.yellow}⚠${COLOR.reset} ${COLOR.dim}${msg}${COLOR.reset}`);
    },
    error({ phase, error }) {
      console.log(`${COLOR.red}✗ Failed at ${phase}: ${error}${COLOR.reset}`);
    },
  };
}
