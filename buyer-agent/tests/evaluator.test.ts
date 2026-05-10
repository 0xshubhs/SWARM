import { describe, expect, it, vi } from "vitest";
import { evaluateResponse } from "../src/reasoning/evaluator.js";
import type { LLMClient } from "../src/types.js";

function fakeLLM(reply: string): LLMClient {
  return { complete: vi.fn(async () => reply) } as unknown as LLMClient;
}

describe("evaluateResponse", () => {
  it("parses a numeric score from the model output", async () => {
    const score = await evaluateResponse({
      task: "t",
      probe: "p",
      response: "r",
      llm: fakeLLM("0.87"),
    });
    expect(score).toBeCloseTo(0.87, 2);
  });

  it("clamps invalid output to 0.5", async () => {
    const score = await evaluateResponse({
      task: "t",
      probe: "p",
      response: "r",
      llm: fakeLLM("not a number"),
    });
    expect(score).toBe(0.5);
  });

  it("rejects scores outside [0,1]", async () => {
    const score = await evaluateResponse({
      task: "t",
      probe: "p",
      response: "r",
      llm: fakeLLM("1.7"),
    });
    expect(score).toBe(0.5);
  });
});
