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
    
    # OpenMetadata connection config (Support OM_API / OM_TOKEN as specified in integration doc)
    om_api_raw: str = os.getenv("OM_API", os.getenv("OPENMETADATA_SERVER_URL", "https://c3-app-009.duckdns.org/"))
    openmetadata_jwt_token: str = os.getenv("OM_TOKEN", os.getenv("OPENMETADATA_JWT_TOKEN", ""))
    
    @property
    def openmetadata_base_url(self) -> str:
        base = self.om_api_raw.rstrip("/")
        if not base.endswith("/api/v1") and not base.endswith("/v1"):
            base = f"{base}/api/v1"
        elif base.endswith("/v1") and not base.endswith("/api/v1"):
            base = base[:-3] + "/api/v1"
        return base

    @property
    def openmetadata_url(self) -> str:
        return self.openmetadata_base_url

    # Heuristic Thresholds (LLD Section 11 & 24)
    unique_threshold: float = float(os.getenv("UNIQUE_THRESHOLD", "0.99"))
    max_allowed_cardinality: int = int(os.getenv("MAX_ALLOWED_CARDINALITY", "20"))
    min_row_count_for_rules: int = int(os.getenv("MIN_ROW_COUNT_FOR_RULES", "1"))

settings = Settings()
