import "dotenv/config";

import { buildAgent } from "./agent.js";
import { createStdoutNarrator } from "./narrator/stdout.js";
import { createAnthropicClient } from "./reasoning/llm_client.js";
import { config } from "./config.js";

async function main() {
  const task = process.argv.slice(2).join(" ").trim();
  if (!task) {
    console.error('Usage: pnpm dev -- "<task description>"');
    process.exit(1);
  }

  const narrator = createStdoutNarrator();
  const agent = buildAgent(narrator, {
    llm: createAnthropicClient(config.llm.apiKey, config.llm.model),
  });
  const result = await agent.run(task);
  process.exit(result.status === "success" ? 0 : 1);
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
