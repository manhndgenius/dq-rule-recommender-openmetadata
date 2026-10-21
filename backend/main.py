"""Main FastAPI application."""

import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)

# Ensure workspace root is in sys.path when running `python backend/main.py`
_ROOT_DIR = Path(__file__).resolve().parents[1]
if str(_ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(_ROOT_DIR))

from backend.api.router import (
    routes_advanced_rules,
    routes_context,
    routes_datasource,
    routes_evaluation,
    routes_generation_jobs,
    routes_nt_rules,
    routes_nt_application_jobs,
    routes_nt_runs,
    routes_recommendation,
    routes_review,
    routes_statistical_rules,
    routes_test_cases,
    routes_target_scopes,
)
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings


def create_app() -> FastAPI:
    """Tạo FastAPI application."""
    app = FastAPI(
        title="Data Quality Rule Recommender & Observability API",
        description=(
            "Backend API kết nối OpenMetadata để lấy schema, profiling và "
            "sinh đề xuất Data Quality rules."
        ),
        version="2.0.0",
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # Include all routers
    app.include_router(routes_datasource.router)
    app.include_router(routes_context.router)
    app.include_router(routes_recommendation.router)
    app.include_router(routes_review.router)
    app.include_router(routes_evaluation.router)
    app.include_router(routes_advanced_rules.router)
    app.include_router(routes_statistical_rules.router)
    app.include_router(routes_test_cases.router)
    app.include_router(routes_target_scopes.router)
    app.include_router(routes_generation_jobs.router)
    app.include_router(routes_nt_rules.router)
    app.include_router(routes_nt_application_jobs.router)
    app.include_router(routes_nt_runs.router)

    return app


app = create_app()


if __name__ == "__main__":
    import os

    host = "127.0.0.1"
    reload = os.getenv("APP_ENV", "development") == "development"
    uvicorn.run("backend.main:app", host=host, port=8000, reload=reload)
