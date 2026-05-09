# worker

GPU compression + inference service. See [`../docs/03_TURBOQUANT_WORKER.md`](../docs/03_TURBOQUANT_WORKER.md).

```bash
# CPU dev (no vLLM/lmcache)
uv sync
cp .env.example .env
uv run uvicorn worker.main:app --reload --port 8001

# GPU prod (RunPod)
uv sync --extra gpu
docker build -t agentvault-worker .
```
