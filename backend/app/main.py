from fastapi import FastAPI

from app.config import settings
from app.routers.analysis_router import router as analysis_router
from app.routers.backtests_router import router as backtests_router
from app.routers.dashboard_router import router as dashboard_router
from app.routers.data_quality_router import router as data_quality_router
from app.routers.demo_router import router as demo_router
from app.routers.groups_router import router as groups_router
from app.routers.health_router import router as health_router
from app.routers.ingestion_router import router as ingestion_router
from app.routers.matches_router import router as matches_router
from app.routers.ml_router import router as ml_router
from app.routers.model_runs_router import router as model_runs_router
from app.routers.odds_router import router as odds_router
from app.routers.predictions_router import router as predictions_router
from app.routers.value_edges_router import router as value_edges_router
from app.routers.research_routes import router as research_router

app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    description="Sports ML research lab for predictions, grouping, and backtesting.",
)

app.include_router(health_router)
app.include_router(demo_router)
app.include_router(matches_router)
app.include_router(ml_router)
app.include_router(predictions_router)
app.include_router(groups_router)
app.include_router(backtests_router)
app.include_router(dashboard_router)
app.include_router(model_runs_router)
app.include_router(odds_router)
app.include_router(value_edges_router)
app.include_router(analysis_router)
app.include_router(data_quality_router)
app.include_router(ingestion_router)
app.include_router(research_router)


@app.get("/")
def root() -> dict:
    return {
        "message": "Welcome to Sports Intelligence Lab",
        "docs": "/docs",
    }