from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.health import HealthStatus, DatabaseHealthStatus
from app.services.health import check_database_health, check_full_health

router = APIRouter()


@router.get("/health", response_model=HealthStatus, tags=["Health"])
@router.get("/api/health", response_model=HealthStatus, tags=["Health"])
def get_health(db: Session = Depends(get_db)) -> HealthStatus:
    return check_full_health(db)


@router.get("/api/health/database", response_model=DatabaseHealthStatus, tags=["Health"])
def get_database_health(db: Session = Depends(get_db)) -> DatabaseHealthStatus:
    health = check_database_health(db)
    if health.status != "healthy":
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=health.model_dump()
        )
    return health
