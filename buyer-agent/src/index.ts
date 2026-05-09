import "dotenv/config";

/**
 * Autonomous buyer agent entry point.
 * See docs/06_BUYER_AGENT.md for the eight-phase pipeline:
 *   classify → discover → evaluate → decide → purchase → fetch → load → execute.
 */
async function main() {
  const task = process.argv.slice(2).join(" ").trim();
  if (!task) {
    console.error("Usage: pnpm dev -- <task description>");
    process.exit(1);
  }
  console.log(`[buyer-agent] task: ${task}`);
  console.log("[buyer-agent] TODO: implement phases 1-8 (see docs/06_BUYER_AGENT.md §2)");
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
