import type { Listing } from "../types.js";

export interface ScoredCandidate {
  listing: Listing;
  score: number;
  response: string;
  tx: string;
}

export interface DecisionConstraints {
  maxBudgetUsdc: number; // remaining budget in micro-USDC
  minScore?: number;
}

export function pickWinner(
  scored: ScoredCandidate[],
  constraints: DecisionConstraints,
): ScoredCandidate | null {
  const minScore = constraints.minScore ?? 0.5;
  const eligible = scored.filter(
    (s) =>
      s.score >= minScore &&
      Number(s.listing.priceUsdc) <= constraints.maxBudgetUsdc,
  );
  if (eligible.length === 0) return null;
  eligible.sort((a, b) => {
    if (Math.abs(a.score - b.score) > 0.05) return b.score - a.score;
    return Number(a.listing.priceUsdc) - Number(b.listing.priceUsdc);
  });
  return eligible[0]!;
}
