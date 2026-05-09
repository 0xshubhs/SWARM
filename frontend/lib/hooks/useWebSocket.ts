"use client";
import { useEffect, useRef, useState } from "react";

interface UseWSOptions {
  url: string | null;
  token: string | null;
  onMessage: (msg: any) => void;
  onClose?: (code: number, reason: string) => void;
}

export function useWebSocket({ url, token, onMessage, onClose }: UseWSOptions) {
  const [connected, setConnected] = useState(false);
  const reconnectAttempts = useRef(0);
  const onMessageRef = useRef(onMessage);
  onMessageRef.current = onMessage;

  useEffect(() => {
    if (!url || !token) return;
    let cancelled = false;
    let ws: WebSocket | null = null;
    let timer: ReturnType<typeof setTimeout> | null = null;

    function connect() {
      if (cancelled) return;
      ws = new WebSocket(`${url}?token=${token}`);
      ws.onopen = () => {
        reconnectAttempts.current = 0;
        setConnected(true);
      };
      ws.onmessage = (e) => {
        try {
          onMessageRef.current(JSON.parse(e.data));
        } catch {
          /* ignore parse errors */
        }
      };
      ws.onclose = (e) => {
        setConnected(false);
        if (cancelled) return;
        if (e.code === 1000 || (e.code >= 4000 && e.code < 5000)) {
          onClose?.(e.code, e.reason);
          return;
        }
        const delay = Math.min(30_000, 1000 * 2 ** reconnectAttempts.current);
        reconnectAttempts.current += 1;
        timer = setTimeout(connect, delay);
      };
      ws.onerror = () => ws?.close();
    }

    connect();
    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      ws?.close();
    };
  }, [url, token, onClose]);

  return { connected };
}
