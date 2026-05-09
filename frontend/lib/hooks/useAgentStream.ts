"use client";
import { useEffect, useState, useRef } from "react";
import { AGENT_WS_URL, BACKEND_URL } from "../constants";

export interface AgentEvent {
  ts: number;
  type: string;
  data: any;
}

interface UseAgentStreamReturn {
  events: AgentEvent[];
  result: string | null;
  running: boolean;
  error: string | null;
}

export function useAgentStream(
  task: string | null,
  wsToken: string | null,
): UseAgentStreamReturn {
  const [events, setEvents] = useState<AgentEvent[]>([]);
  const [result, setResult] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    if (!task || !wsToken) return;
    setEvents([]);
    setResult(null);
    setError(null);
    setRunning(true);

    let cancelled = false;
    let ws: WebSocket | null = null;

    (async () => {
      try {
        const resp = await fetch(`${BACKEND_URL}/v1/agent/runs`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ task }),
        });
        const { run_id } = await resp.json();
        if (cancelled) return;
        ws = new WebSocket(
          `${AGENT_WS_URL}/v1/ws/agent/${run_id}?token=${wsToken}`,
        );
        wsRef.current = ws;
        ws.onmessage = (e) => {
          const msg = JSON.parse(e.data);
          setEvents((prev) => [...prev, msg]);
          if (msg.type === "agent.execute.done") setResult(msg.data.output);
          if (msg.type === "agent.complete") {
            setRunning(false);
            ws?.close();
          }
          if (msg.type === "agent.error") {
            setError(msg.data.error);
            setRunning(false);
            ws?.close();
          }
        };
      } catch (e: any) {
        setError(e?.message ?? "agent run failed to start");
        setRunning(false);
      }
    })();

    return () => {
      cancelled = true;
      ws?.close();
      setRunning(false);
    };
  }, [task, wsToken]);

  return { events, result, running, error };
}
