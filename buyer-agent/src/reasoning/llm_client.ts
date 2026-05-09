import type { LLMClient } from "../types.js";

/**
 * Minimal Anthropic-compatible client. We hit the Messages API directly via
 * fetch — keeps the dependency surface small, and we don't need streaming
 * for these short reasoning calls.
 */
export function createAnthropicClient(apiKey: string, model = "claude-sonnet-4"): LLMClient {
  return {
    async complete({ system, user, maxTokens = 1000 }) {
      if (!apiKey) {
        // Hackathon-mode fallback so the agent can run without an API key.
        return JSON.stringify({
          tags: ["anchor", "solana", "rust"],
          domain: "code-generation",
          complexity: "moderate",
        });
      }
      const r = await fetch("https://api.anthropic.com/v1/messages", {
        method: "POST",
        headers: {
          "x-api-key": apiKey,
          "anthropic-version": "2023-06-01",
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          model,
          max_tokens: maxTokens,
          system,
          messages: [{ role: "user", content: user }],
        }),
      });
      if (!r.ok) {
        throw new Error(`Anthropic ${r.status}: ${await r.text()}`);
      }
      const data = (await r.json()) as { content?: Array<{ type: string; text?: string }> };
      const blocks = data.content ?? [];
      return blocks
        .filter((b) => b.type === "text" && b.text)
        .map((b) => b.text!)
        .join("");
    },
  };
}
