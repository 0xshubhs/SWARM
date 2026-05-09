"""Backend settings — pydantic-settings, env-driven."""
from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    ENVIRONMENT: str = "development"
    LOG_LEVEL: str = "info"
    BASE_URL: str = "http://localhost:8000"
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # Database / Redis. Required in prod; safe defaults for dev.
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/agentvault"
    REDIS_URL: str = "redis://localhost:6379"

    # Solana
    SOLANA_NETWORK: str = "devnet"
    SOLANA_RPC_URL: str = "https://api.devnet.solana.com"
    SOLANA_WS_URL: str = "wss://api.devnet.solana.com"
    AGENTVAULT_PROGRAM_ID: str = "AgntVau1tVau1tVau1tVau1tVau1tVau1tVau1tVau1"
    USDC_MINT: str = "4zMMC9srt5Ri5X14GAgXhaHii3GnPAEERYPJgZJDncDU"
    PLATFORM_TREASURY: str = "11111111111111111111111111111111"

    # Auth secrets
    WS_TOKEN_SECRET: str = "dev-secret-change-me"

    # x402
    X402_FACILITATOR_URL: str = "https://facilitator.payai.network"

    # Bundlr/Irys sidecar (a small Node service that wraps @irys/sdk)
    IRYS_SIDECAR_URL: str = "http://localhost:3030"

    # TurboQuant worker
    WORKER_URL: str = "http://localhost:9000"
    WORKER_API_KEY: str = "dev-worker-key"

    # vLLM runtime (RunPod or local Cloudflare-tunneled)
    VLLM_ENDPOINT: str = "http://localhost:8000"
    VLLM_API_KEY: str = ""

    # Pricing constants (USDC micro-units, 6 decimals)
    BASE_FEE_USDC: int = Field(default=500_000)
    PER_MB_COMPUTE_USDC: int = Field(default=100_000)
    PER_MB_STORAGE_USDC: int = Field(default=50_000)

    # Pagination
    MAX_PAGE_SIZE: int = 100
    DEFAULT_PAGE_SIZE: int = 20


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
