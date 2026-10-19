import os
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

# Load .env file from backend directory or workspace root
env_path = Path(__file__).resolve().parents[1] / ".env"
load_dotenv(dotenv_path=env_path)


class Settings(BaseModel):
    app_env: str = os.getenv("APP_ENV", "development")
    api_prefix: str = "/api/v1"

    # OpenMetadata connection config
    om_api_raw: str = os.getenv("OM_API", "")
    openmetadata_jwt_token: str = os.getenv("OM_TOKEN", "")
    postgres_host: str = os.getenv("POSTGRES_HOST", "localhost")
    postgres_port: int = int(os.getenv("POSTGRES_PORT", "5432"))
    postgres_user: str = os.getenv("POSTGRES_USER", "postgres")
    postgres_password: str = os.getenv("POSTGRES_PASSWORD", "")
    postgres_db: str = os.getenv("POSTGRES_DB", "dq_rules")
    postgres_connect_timeout: int = int(
        os.getenv("POSTGRES_CONNECT_TIMEOUT", "5")
    )

    @property
    def openmetadata_base_url(self) -> str:
        if not self.om_api_raw:
            return ""
        base = self.om_api_raw.rstrip("/")
        if not base.endswith("/api/v1") and not base.endswith("/v1"):
            base = f"{base}/api/v1"
        elif base.endswith("/v1") and not base.endswith("/api/v1"):
            base = base[:-3] + "/api/v1"
        return base

    @property
    def openmetadata_url(self) -> str:
        return self.openmetadata_base_url

    # Heuristic Thresholds
    unique_threshold: float = float(os.getenv("UNIQUE_THRESHOLD", "0.99"))
    max_allowed_cardinality: int = int(os.getenv("MAX_ALLOWED_CARDINALITY", "20"))
    min_row_count_for_rules: int = int(os.getenv("MIN_ROW_COUNT_FOR_RULES", "1"))


settings = Settings()
