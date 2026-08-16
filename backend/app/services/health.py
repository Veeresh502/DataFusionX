import redis
from typing import Dict, Any
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.schemas.health import HealthStatus, DatabaseHealthStatus
from app.core.config import settings
from app.core.celery_app import celery_app


def check_database_health(db: Session) -> DatabaseHealthStatus:
    try:
        db.execute(text("SELECT 1"))
        return DatabaseHealthStatus(status="healthy", database="connected")
    except Exception as e:
        return DatabaseHealthStatus(status="unhealthy", database=f"disconnected: {str(e)}")


def check_redis_health() -> str:
    try:
        r = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_timeout=1.5)
        if r.ping():
            return "healthy"
        return "unhealthy"
    except Exception:
        return "unhealthy"


def check_celery_health() -> str:
    try:
        insp = celery_app.control.inspect(timeout=1.5)
        ping_res = insp.ping()
        if ping_res and len(ping_res) > 0:
            return "healthy"
        return "unhealthy"
    except Exception:
        return "unhealthy"


def check_full_health(db: Session) -> HealthStatus:
    db_status = "healthy"
    try:
        db.execute(text("SELECT 1"))
    except Exception:
        db_status = "unhealthy"

    redis_status = check_redis_health()
    celery_status = check_celery_health()

    overall = "healthy"
    if db_status != "healthy" or redis_status != "healthy" or celery_status != "healthy":
        if db_status == "unhealthy" and redis_status == "unhealthy":
            overall = "unhealthy"
        else:
            overall = "degraded"

    return HealthStatus(
        status=overall,
        database=db_status,
        redis=redis_status,
        celery=celery_status,
        version=getattr(settings, "VERSION", "0.6.0")
    )
