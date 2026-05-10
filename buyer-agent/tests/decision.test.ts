import { describe, expect, it } from "vitest";
import { pickWinner, type ScoredCandidate } from "../src/reasoning/decision.js";

function listing(id: string, priceUsdc: number, sandbox = 0): ScoredCandidate["listing"] {
  return {
    id,
    seller: "S",
    title: "t",
    modelId: "qwen2.5-7b-instruct",
    tags: [],
    priceUsdc: BigInt(priceUsdc) as unknown as number,
    sandboxPriceUsdc: BigInt(sandbox) as unknown as number,
    arweaveTx: "x".repeat(43),
    contentHashHex: "00".repeat(32),
    quantSeed: 0,
    bitsPerChannel: 35,
    seqLen: 0,
    active: true,
    purchases: 0,
    createdAt: new Date().toISOString(),
  } as any;
}

describe("pickWinner", () => {
  it("returns null when nothing meets minScore", () => {
    const scored: ScoredCandidate[] = [
      { listing: listing("a", 1), score: 0.4, response: "", tx: "" },
    ];
    expect(pickWinner(scored, { maxBudgetUsdc: 1_000_000 })).toBeNull();
  });

  it("filters out candidates above budget", () => {
    const scored: ScoredCandidate[] = [
      { listing: listing("a", 100_000_000), score: 0.9, response: "", tx: "" },
      { listing: listing("b", 5_000_000), score: 0.7, response: "", tx: "" },
    ];
    const winner = pickWinner(scored, { maxBudgetUsdc: 10_000_000 });
    expect(winner?.listing.id).toBe("b");
  });

  it("prefers higher score when score gap > 0.05", () => {
    const scored: ScoredCandidate[] = [
      { listing: listing("cheap", 1_000_000), score: 0.7, response: "", tx: "" },
      { listing: listing("better", 5_000_000), score: 0.85, response: "", tx: "" },
    ];
    const winner = pickWinner(scored, { maxBudgetUsdc: 10_000_000 });
    expect(winner?.listing.id).toBe("better");
  });

  it("breaks score ties by cheaper price", () => {
    const scored: ScoredCandidate[] = [
      { listing: listing("expensive", 9_000_000), score: 0.81, response: "", tx: "" },
      { listing: listing("cheap", 2_000_000), score: 0.79, response: "", tx: "" },
    ];
    const winner = pickWinner(scored, { maxBudgetUsdc: 10_000_000 });
    expect(winner?.listing.id).toBe("cheap");
  });

  it("respects custom minScore", () => {
    const scored: ScoredCandidate[] = [
      { listing: listing("a", 1_000_000), score: 0.6, response: "", tx: "" },
    ];
    expect(pickWinner(scored, { maxBudgetUsdc: 5_000_000, minScore: 0.7 })).toBeNull();
    expect(pickWinner(scored, { maxBudgetUsdc: 5_000_000, minScore: 0.5 })).not.toBeNull();
  });
});
