from fastapi import FastAPI, Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session

from app.core.config import settings
from app.api.router import api_router
from app.schemas.health import HealthStatus
from app.db.session import get_db
from app.services.health import check_full_health
from app.core.prometheus import PrometheusMiddleware, get_metrics_response

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

# Prometheus HTTP Metrics Middleware
app.add_middleware(PrometheusMiddleware)

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
def health_root(db: Session = Depends(get_db)) -> HealthStatus:
    return check_full_health(db)


# Prometheus metrics endpoint: GET /metrics
@app.get("/metrics", tags=["Monitoring"])
def metrics():
    return get_metrics_response()


# Include API Router for /api/* endpoints
app.include_router(api_router)
