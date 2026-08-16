from fastapi import APIRouter
from app.api.endpoints import health, auth, projects, data_sources, pipelines, warehouse, websocket, schedules, monitoring, ai

api_router = APIRouter()
api_router.include_router(health.router)
api_router.include_router(auth.router, prefix="/api/auth")
api_router.include_router(projects.router, prefix="/api")
api_router.include_router(data_sources.router, prefix="/api/sources")
api_router.include_router(data_sources.router, prefix="/api/datasets")
api_router.include_router(pipelines.router, prefix="/api/pipelines")
api_router.include_router(warehouse.router, prefix="/api/warehouse")
api_router.include_router(schedules.router, prefix="/api/schedules")
api_router.include_router(monitoring.router, prefix="/api/monitoring")
api_router.include_router(ai.router, prefix="/api/ai", tags=["ai"])
api_router.include_router(websocket.router)









