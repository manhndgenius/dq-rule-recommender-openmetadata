"""Main FastAPI application."""

from backend.api.router import (
    routes_advanced_rules,
    routes_context,
    routes_datasource,
    routes_evaluation,
    routes_recommendation,
    routes_review,
)
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include all routers
    app.include_router(routes_datasource.router)
    app.include_router(routes_context.router)
    app.include_router(routes_recommendation.router)
    app.include_router(routes_review.router)
    app.include_router(routes_evaluation.router)
    app.include_router(routes_advanced_rules.router)

    return app


app = create_app()


if __name__ == "__main__":
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8000, reload=True)
