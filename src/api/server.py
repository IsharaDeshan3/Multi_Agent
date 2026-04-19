from __future__ import annotations

from fastapi import FastAPI

from src.api.routes.agents import router as agents_router
from src.api.routes.contracts import router as contracts_router
from src.api.routes.health import router as health_router
from src.api.routes.pipelines import router as pipelines_router

app = FastAPI(
    title="Parser-First Research Review API",
    version="0.1.0",
    description="Parser-first LangGraph foundation with shared ReviewState contract.",
)

app.include_router(health_router)
app.include_router(contracts_router)
app.include_router(agents_router)
app.include_router(pipelines_router)


@app.get("/")
def root() -> dict[str, str]:
    """Root endpoint for quick sanity checks."""
    return {"message": "Multi-Agent Research Review API is running."}
