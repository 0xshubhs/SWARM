import { describe, expect, it, vi } from "vitest";
import { classifyTask } from "../src/reasoning/classifier.js";
import type { LLMClient } from "../src/types.js";

function fakeLLM(reply: string): LLMClient {
  return {
    complete: vi.fn(async () => reply),
  } as unknown as LLMClient;
}

describe("classifyTask", () => {
  it("parses raw JSON", async () => {
    const llm = fakeLLM(`{"tags":["solana","anchor"],"domain":"code","complexity":"moderate"}`);
    const out = await classifyTask("write a pda fn", llm);
    expect(out.tags).toEqual(["solana", "anchor"]);
    expect(out.domain).toBe("code");
    expect(out.complexity).toBe("moderate");
  });

  it("strips ```json fences", async () => {
    const llm = fakeLLM("```json\n{\"tags\":[\"x\"],\"domain\":\"d\",\"complexity\":\"simple\"}\n```");
    const out = await classifyTask("t", llm);
    expect(out.tags).toEqual(["x"]);
  });

  it("falls back to a safe default on garbage output", async () => {
    const llm = fakeLLM("the model went sideways");
    const out = await classifyTask("t", llm);
    expect(out.tags).toEqual(["general"]);
    expect(out.domain).toBe("unknown");
    expect(out.complexity).toBe("moderate");
  });
});
