from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import settings
from app.api.router import api_router
from app.schemas.health import HealthStatus

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# CORS Middleware
if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.BACKEND_CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Direct /health endpoint as required by spec: GET /health
@app.get("/health", response_model=HealthStatus, tags=["Health"])
def health_root() -> HealthStatus:
    return HealthStatus(status="healthy")

# Include API Router for /api/health/database etc.
app.include_router(api_router)
