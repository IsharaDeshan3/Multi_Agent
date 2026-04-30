from __future__ import annotations

import os

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.agents import router as agents_router
from src.api.routes.contracts import router as contracts_router
from src.api.routes.health import router as health_router
from src.api.routes.pipelines import router as pipelines_router
from src.api.routes.source_summary import router as source_summary_router

app = FastAPI(
    title="Parser-First Research Review API",
    version="0.1.0",
    description="Parser-first LangGraph foundation with shared ReviewState contract.",
)

default_frontend_origins = "http://localhost:3000,http://localhost:3001"
local_dev_origin_regex = r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$"
frontend_origins = [
    origin.strip()
    for origin in (os.getenv("FRONTEND_ORIGINS") or default_frontend_origins).split(",")
    if origin.strip()
]
if frontend_origins:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_origin_regex=local_dev_origin_regex,
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(health_router)
app.include_router(contracts_router)
app.include_router(agents_router)
app.include_router(pipelines_router)
app.include_router(source_summary_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint for quick sanity checks."""
    return {"message": "Multi-Agent Research Review API is running."}
