import type { Listing, Narrator } from "../types.js";

export function createWSPublisherNarrator(
  backendUrl: string,
  runId: string,
  publishToken: string,
): Narrator {
  async function publish(type: string, data: unknown): Promise<void> {
    try {
      await fetch(`${backendUrl}/internal/publish`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${publishToken}`,
        },
        body: JSON.stringify({
          channel: `events:agent:${runId}`,
          type,
          data,
        }),
      });
    } catch (err) {
      // fire-and-forget; don't block the agent on publish failures
      console.error(`[narrator] publish ${type} failed:`, err);
    }
  }

  function previewOf(c: Listing) {
    return {
      id: c.address,
      title: c.title,
      price: Number(c.priceUsdc),
      purchases: c.purchases,
    };
  }

  return {
    start: (d) => void publish("agent.start", d),
    classify: (d) => void publish("agent.classify", d),
    discover: (candidates) =>
      void publish("agent.discover", { candidates: candidates.map(previewOf) }),
    sandboxStart: (d) => void publish("agent.sandbox.start", d),
    sandboxX402: (d) => void publish("agent.sandbox.x402", d),
    sandboxResponse: (d) => void publish("agent.sandbox.response", d),
    decision: (d) => void publish("agent.decision", d),
    purchaseSigning: (d) => void publish("agent.purchase.signing", d),
    purchaseConfirmed: (d) => void publish("agent.purchase.confirmed", d),
    fetchProgress: () => undefined,
    fetchDone: (d) => void publish("agent.fetch.arweave", d),
    verifyHash: (d) => void publish("agent.verify.hash", d),
    decompress: (d) => void publish("agent.decompress", d),
    executeStart: (d) => void publish("agent.execute.start", d),
    executeToken: (token) => void publish("agent.execute.token", { token }),
    executeDone: (d) => void publish("agent.execute.done", d),
    complete: (d) => void publish("agent.complete", d),
    warn: (msg) => void publish("agent.warn", { message: msg }),
    error: (d) => void publish("agent.error", d),
  };
}
