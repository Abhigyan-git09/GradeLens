"""GradeLens backend configuration."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from ``GRADELENS_*`` variables."""

    APP_VERSION: str = "0.2.0"
    ENVIRONMENT: Literal["development", "test", "production"] = "development"
    LOG_LEVEL: str = "INFO"

    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DB_PATH: Path = BASE_DIR / "gradelens.db"
    MODEL_DIR: Path = BASE_DIR / "ml" / "artifacts"

    # A production container should point this at persistent storage, for
    # example sqlite:////data/gradelens.db.
    DATABASE_URL: str = ""

    # Demo-data generation and model training are intentionally independent.
    # Production can seed an empty volume while requiring packaged artifacts.
    SEED_DEMO_DATA_IF_EMPTY: bool = True
    TRAIN_MODELS_ON_STARTUP: bool = True
    STRICT_STARTUP: bool = False

    # CORS is only needed when the browser calls a different API origin.
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:5174",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "http://127.0.0.1:5174",
    ]

    # API safety. The production reverse proxy injects the write key
    # server-side; it is never included in the browser bundle.
    WRITE_API_KEY: str = ""
    MAX_REQUEST_BYTES: int = Field(default=1_000_000, ge=16_384)
    RATE_LIMIT_PER_MINUTE: int = Field(default=600, ge=1)
    MUTATION_RATE_LIMIT_PER_MINUTE: int = Field(default=60, ge=1)

    # Model settings
    RISK_THRESHOLD: float = Field(default=0.6, ge=0.0, le=1.0)
    SPEC_DEVIATION_PCT: float = Field(default=2.5, gt=0.0)
    PREDICTION_HORIZONS: list[int] = [30, 60, 120]

    # Recommendation engine weights
    REC_WEIGHT_RISK: float = 0.5
    REC_WEIGHT_STABILIZATION: float = 0.3
    REC_WEIGHT_CHANGE: float = 0.2

    # Optional natural-language explanation provider. The deterministic,
    # evidence-grounded explainer remains available when no key is configured.
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "gpt-5.6-luna"
    LLM_BASE_URL: str = "https://api.openai.com/v1"
    LLM_TIMEOUT_SECONDS: float = Field(default=8.0, gt=0.0, le=60.0)

    model_config = SettingsConfigDict(
        env_prefix="GRADELENS_",
        case_sensitive=False,
        extra="ignore",
    )

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH}"


settings = Settings()
