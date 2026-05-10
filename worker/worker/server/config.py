"""Server configuration via environment variables."""
from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    WORKER_API_KEY: str = "dev-secret-change-me"
    HOST: str = "0.0.0.0"
    PORT: int = 8001
    VLLM_ENDPOINT: str = "http://localhost:8000"
    HF_MODEL_ID: str = "Qwen/Qwen2.5-7B-Instruct"
    TURBOQUANT_BITS: float = 3.5
    HF_TOKEN: str | None = None

    CUDA_VISIBLE_DEVICES: str | None = None

    @property
    def vllm_url(self) -> str:
        return f"{self.VLLM_ENDPOINT}/v1/completions"


settings = Settings()