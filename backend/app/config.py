"""GradeLens Backend Configuration."""

from pathlib import Path
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Project paths
    BASE_DIR: Path = Path(__file__).resolve().parent.parent
    DB_PATH: Path = BASE_DIR / "gradelens.db"
    MODEL_DIR: Path = BASE_DIR / "ml" / "artifacts"

    # Database
    DATABASE_URL: str = ""

    # CORS — opened to Vercel origin in production
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://localhost:3000",
        "http://127.0.0.1:5173",
        "*"
    ]

    # Model settings
    RISK_THRESHOLD: float = 0.6
    SPEC_DEVIATION_PCT: float = 2.5  # ±2.5% from setpoint
    PREDICTION_HORIZONS: list[int] = [30, 60, 120]  # seconds

    # Recommendation engine weights
    REC_WEIGHT_RISK: float = 0.5
    REC_WEIGHT_STABILIZATION: float = 0.3
    REC_WEIGHT_CHANGE: float = 0.2

    model_config = {"env_prefix": "GRADELENS_"}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        if not self.DATABASE_URL:
            self.DATABASE_URL = f"sqlite:///{self.DB_PATH}"


settings = Settings()
