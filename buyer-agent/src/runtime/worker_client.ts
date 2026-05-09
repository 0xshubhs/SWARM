export interface DecompressLoadParams {
  blob: Buffer;
  metadata: any;
  modelId: string;
}

export interface InferenceStreamParams {
  cache_id: string;
  prompt: string;
  max_tokens: number;
  on_token: (token: string) => void;
}

export class WorkerClient {
  constructor(public workerUrl: string, public apiKey: string) {}

  async decompressAndLoad(params: DecompressLoadParams): Promise<string> {
    if (!this.workerUrl || this.workerUrl.includes("localhost:9000")) {
      // Hackathon-mode: pretend we loaded into vLLM's KV cache.
      return `cache_${Date.now()}`;
    }
    const form = new FormData();
    form.append("blob", new Blob([new Uint8Array(params.blob)]));
    form.append("metadata", JSON.stringify(params.metadata));
    form.append("model_id", params.modelId);
    const r = await fetch(`${this.workerUrl}/decompress_and_load`, {
      method: "POST",
      headers: this.apiKey ? { "X-API-Key": this.apiKey } : {},
      body: form,
    });
    if (!r.ok) throw new Error(`worker error ${r.status}: ${await r.text()}`);
    const data = (await r.json()) as { cache_id: string };
    return data.cache_id;
  }

  async inferenceStream(params: InferenceStreamParams): Promise<string> {
    if (!this.workerUrl || this.workerUrl.includes("localhost:9000")) {
      // Stream a deterministic mock so the demo still produces visible output.
      const stub = `Loaded memory; producing response for: ${params.prompt}`;
      for (const tok of stub.split(/(\s+)/)) {
        params.on_token(tok);
        await new Promise((r) => setTimeout(r, 25));
      }
      return stub;
    }

    const r = await fetch(`${this.workerUrl}/inference_stream`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...(this.apiKey ? { "X-API-Key": this.apiKey } : {}),
      },
      body: JSON.stringify(params),
    });

    const reader = r.body!.getReader();
    const decoder = new TextDecoder();
    let buffer = "";
    let full = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const events = buffer.split("\n\n");
      buffer = events.pop() ?? "";
      for (const event of events) {
        const line = event.split("\n").find((l) => l.startsWith("data: "));
        if (!line) continue;
        const data = JSON.parse(line.slice(6));
        if (data.type === "token") {
          params.on_token(data.token);
          full += data.token;
        } else if (data.type === "done") {
          return data.output ?? full;
        }
      }
    }
    return full;
  }
}
