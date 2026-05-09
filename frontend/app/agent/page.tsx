"use client";
import { useState } from "react";
import { Play, RotateCcw } from "lucide-react";

import { Card, CardContent } from "@/components/ui/Card";
import { Input } from "@/components/ui/Input";
import { Button } from "@/components/ui/Button";
import { useAgentStream } from "@/lib/hooks/useAgentStream";

const DEFAULT_TASK = "Write a production Anchor PDA derivation function";

export default function AgentDemoPage() {
  const [task, setTask] = useState(DEFAULT_TASK);
  const [running, setRunning] = useState<string | null>(null);
  // For the hackathon demo, we don't gate the WS by signature challenge — use
  // a dummy token so the UI renders even when the backend isn't deployed.
  const stream = useAgentStream(running, "demo-token");

  return (
    <main className="max-w-5xl mx-auto px-6 py-10">
      <header className="mb-8">
        <h1 className="text-4xl font-bold">Live Agent Demo</h1>
        <p className="text-zinc-400 mt-1">
          Watch an autonomous agent discover, evaluate, purchase, and use trained memory — all on Solana.
        </p>
      </header>

      <Card className="mb-6">
        <CardContent className="space-y-4">
          <label className="block text-xs text-zinc-400">Task</label>
          <Input
            value={task}
            onChange={(e) => setTask(e.target.value)}
            disabled={Boolean(running)}
          />
          <div className="flex gap-2">
            <Button onClick={() => setRunning(task)} disabled={Boolean(running)}>
              <Play className="w-4 h-4 mr-2" /> Run agent
            </Button>
            <Button
              variant="outline"
              onClick={() => setRunning(null)}
              disabled={!running}
            >
              <RotateCcw className="w-4 h-4 mr-2" /> Reset
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card className="mb-6">
        <CardContent className="space-y-2 max-h-[600px] overflow-y-auto">
          <h2 className="text-lg font-semibold">Reasoning</h2>
          {stream.events.length === 0 && (
            <p className="text-sm text-zinc-500">
              Hit "Run agent" to stream the buyer agent's decisions in real time.
            </p>
          )}
          {stream.events.map((e, i) => (
            <pre
              key={i}
              className="text-xs whitespace-pre-wrap font-mono text-zinc-400 border-l border-zinc-800 pl-3"
            >
              <span className="text-violet-400">{e.type}</span>{" "}
              {JSON.stringify(e.data)}
            </pre>
          ))}
          {stream.error && (
            <p className="text-sm text-red-400 mt-2">Error: {stream.error}</p>
          )}
        </CardContent>
      </Card>

      {stream.result && (
        <Card>
          <CardContent>
            <h2 className="text-lg font-semibold text-emerald-400 mb-2">Result</h2>
            <pre className="text-sm whitespace-pre-wrap">{stream.result}</pre>
          </CardContent>
        </Card>
      )}
    </main>
  );
}
