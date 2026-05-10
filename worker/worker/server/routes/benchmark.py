"""POST /benchmark — trigger quality benchmark on Qwen model."""
from __future__ import annotations

import json

from fastapi import APIRouter, Body, Form, HTTPException
from pydantic import BaseModel

router = APIRouter()


class BenchmarkResponse(BaseModel):
    status: str
    results_path: str | None = None
    summary: dict | None = None


@router.post("/benchmark")
async def benchmark_endpoint(
    file: bytes | None = Body(default=None),
    model: str = Form("Qwen/Qwen2.5-7B-Instruct"),
) -> BenchmarkResponse:
    """Run TurboQuant quality benchmark.

    If file is provided, it should be a JSON: {"prompts": ["p1", ...]}
    Otherwise uses built-in eval prompts.
    """
    if file:
        try:
            prompts_data = json.loads(file.decode())
            prompts = prompts_data.get("prompts", [])
            if not prompts:
                raise ValueError("No prompts in JSON")
        except Exception as e:
            raise HTTPException(400, f"Invalid prompts file: {e}")
    else:
        from benchmarks.quality import EVAL_PROMPTS
        prompts = EVAL_PROMPTS

    output_path = f"/tmp/turboquant_benchmark_{model.replace('/', '_')}.csv"

    try:
        import pandas as pd

        import benchmarks.quality as bq
        bq.main(model, output_path)
        df = pd.read_csv(output_path)
        summary = (
            df.groupby("bits")
            .agg({"compression_ratio": "mean", "first_50_match": "mean", "token_match_rate": "mean"})
            .round(3)
            .to_dict()
        )
        return BenchmarkResponse(status="complete", results_path=output_path, summary=summary)
    except ImportError as e:
        raise HTTPException(503, f"Benchmark dependencies not installed: {e}")
    except Exception as e:
        raise HTTPException(500, f"Benchmark failed: {e}")