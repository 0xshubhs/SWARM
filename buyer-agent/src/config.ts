import "dotenv/config";

export const config = {
  backendUrl: process.env.BACKEND_URL ?? "http://localhost:8000",
  workerUrl: process.env.WORKER_URL ?? "http://localhost:9000",
  workerApiKey: process.env.WORKER_API_KEY ?? "",
  solanaRpcUrl: process.env.SOLANA_RPC_URL ?? "https://api.devnet.solana.com",
  programId:
    process.env.AGENTVAULT_PROGRAM_ID ?? "HvWGEDbnRCVThyCNwUVpFRfWsHx2aqT9Ttotr4QovGCF",
  usdcMint:
    process.env.USDC_MINT ?? "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU",
  treasury: process.env.PLATFORM_TREASURY ?? "11111111111111111111111111111111",
  agentKeypairBase58: process.env.AGENT_KEYPAIR_BS58 ?? "",
  maxBudgetUsdc: Number(process.env.AGENT_MAX_BUDGET_USDC ?? 30),
  llm: {
    provider: process.env.LLM_PROVIDER ?? "anthropic",
    apiKey: process.env.ANTHROPIC_API_KEY ?? process.env.OPENAI_API_KEY ?? "",
    model: process.env.LLM_MODEL ?? "claude-sonnet-4",
  },
};
