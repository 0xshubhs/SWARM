import type { LLMClient } from "../types.js";

export interface EvalInput {
  task: string;
  probe: string;
  response: string;
  llm: LLMClient;
}

export async function evaluateResponse(input: EvalInput): Promise<number> {
  const raw = await input.llm.complete({
    system: `You evaluate agent responses. Score from 0.0 to 1.0 based on:
- Technical accuracy (40%)
- Domain expertise depth (30%)
- Specificity vs generic (20%)
- Code quality if applicable (10%)

Output ONLY the score as a number, e.g., "0.87"`,
    user: `Original task: ${input.task}\nProbe: ${input.probe}\nResponse: ${input.response}\n\nScore:`,
    maxTokens: 10,
  });

  const score = parseFloat(raw.trim());
  if (Number.isNaN(score) || score < 0 || score > 1) return 0.5;
  return score;
}
