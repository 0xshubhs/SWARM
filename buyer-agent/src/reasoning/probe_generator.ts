import type { LLMClient } from "../types.js";

export async function generateProbe(
  task: string,
  tags: string[],
  llm: LLMClient,
): Promise<string> {
  const raw = await llm.complete({
    system: `Given a task, generate a SHORT diagnostic probe query (1-2 sentences) that tests whether an AI agent has expertise in this domain. The probe should be answerable in 100 tokens.`,
    user: `Task: ${task}\nTags: ${tags.join(", ")}\n\nProbe:`,
    maxTokens: 100,
  });
  return raw.trim() || `Tell me, in one paragraph, what makes ${tags[0] ?? "this"} hard.`;
}
