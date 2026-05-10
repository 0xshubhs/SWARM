# RunPod GPU image: CUDA 12.1 + Python 3.12
# Starts vLLM (Qwen 2.5 7B) on port 8000 + FastAPI worker on port 8001
FROM nvidia/cuda:12.1.0-runtime-ubuntu22.04

ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CUDA_VISIBLE_DEVICES=0

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.12 python3-pip curl ca-certificates git \
    && rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv

COPY pyproject.toml ./

RUN uv pip install --system -e . --extra gpu

COPY worker/ worker/
COPY benchmarks/ benchmarks/

EXPOSE 8001 8000

CMD ["bash", "-c", \
     "uv run vllm serve Qwen/Qwen2.5-7B-Instruct " \
     "--kv-cache-dtype fp8 " \
     "--max-model-len 8192 " \
     "--gpu-memory-utilization 0.7 " \
     "--port 8000 " \
     "--host 0.0.0.0 & " \
     "sleep 90 && " \
     "uv run uvicorn worker.main:app --host 0.0.0.0 --port 8001"]