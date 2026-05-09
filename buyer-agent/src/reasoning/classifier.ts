import type { LLMClient } from "../types.js";

export interface ClassifiedTask {
  tags: string[];
  domain: string;
  complexity: "simple" | "moderate" | "complex";
}

const SYSTEM = `You classify AI agent tasks. Output JSON:
{
  "tags": ["string", ...],
  "domain": "string",
  "complexity": "simple" | "moderate" | "complex"
}

Examples:
Task: "Write a production Anchor PDA derivation function"
{"tags":["anchor","solana","rust","pda"],"domain":"code-generation","complexity":"moderate"}

Output ONLY the JSON, no prose.`;

function stripCodeFence(s: string): string {
  return s
    .replace(/^```(?:json)?/i, "")
    .replace(/```$/m, "")
    .trim();
}

export async function classifyTask(task: string, llm: LLMClient): Promise<ClassifiedTask> {
  const raw = await llm.complete({
    system: SYSTEM,
    user: task,
    maxTokens: 200,
    responseFormat: "json",
  });
  try {
    return JSON.parse(stripCodeFence(raw));
  } catch {
    return { tags: ["general"], domain: "unknown", complexity: "moderate" };
  }
}
