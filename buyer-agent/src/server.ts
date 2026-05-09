/**
 * HTTP server for frontend integration. Exposes POST /v1/agent/runs which
 * kicks off a run and returns a run_id; the agent then publishes events to
 * the backend's WS gateway via the WS publisher narrator.
 */
import "dotenv/config";
import http from "node:http";
import { randomUUID } from "node:crypto";

import { buildAgent } from "./agent.js";
import { createWSPublisherNarrator } from "./narrator/ws_publisher.js";
import { createTeeNarrator } from "./narrator/tee.js";
import { createStdoutNarrator } from "./narrator/stdout.js";
import { createAnthropicClient } from "./reasoning/llm_client.js";
import { config } from "./config.js";

const PORT = Number(process.env.AGENT_SERVER_PORT ?? 3030);
const PUBLISH_TOKEN = process.env.AGENT_PUBLISH_TOKEN ?? "dev-secret-change-me";

function readJsonBody<T>(req: http.IncomingMessage): Promise<T> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    req.on("data", (c: Buffer) => chunks.push(c));
    req.on("end", () => {
      try {
        resolve(JSON.parse(Buffer.concat(chunks).toString("utf8")));
      } catch (e) {
        reject(e);
      }
    });
    req.on("error", reject);
  });
}

const server = http.createServer(async (req, res) => {
  res.setHeader("access-control-allow-origin", "*");
  res.setHeader("access-control-allow-headers", "content-type, authorization");
  res.setHeader("access-control-allow-methods", "POST, OPTIONS");

  if (req.method === "OPTIONS") {
    res.statusCode = 204;
    res.end();
    return;
  }

  if (req.method === "POST" && req.url === "/v1/agent/runs") {
    try {
      const body = await readJsonBody<{ task: string }>(req);
      const runId = randomUUID();

      const narrator = createTeeNarrator(
        createStdoutNarrator(),
        createWSPublisherNarrator(config.backendUrl, runId, PUBLISH_TOKEN),
      );
      const agent = buildAgent(narrator, {
        llm: createAnthropicClient(config.llm.apiKey, config.llm.model),
      });

      // fire-and-forget; agent publishes its own events
      void agent.run(body.task).catch((err) => {
        console.error("agent run failed:", err);
      });

      res.statusCode = 200;
      res.setHeader("content-type", "application/json");
      res.end(
        JSON.stringify({ run_id: runId, ws_channel: `/v1/ws/agent/${runId}` }),
      );
      return;
    } catch (e: any) {
      res.statusCode = 400;
      res.end(`bad request: ${e.message}`);
      return;
    }
  }

  res.statusCode = 404;
  res.end("not found");
});

server.listen(PORT, () => {
  console.log(`buyer-agent server listening on :${PORT}`);
});
