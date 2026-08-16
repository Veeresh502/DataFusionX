from typing import Dict, Any, List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.api.deps import get_current_user
from app.services import monitoring_service


router = APIRouter()


@router.get("/overview", tags=["Monitoring"])
def get_monitoring_overview(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

) -> Dict[str, Any]:
    system_health = monitoring_service.get_system_health(db)
    pipeline_overview = monitoring_service.get_pipeline_overview(db, current_user.organization_id)
    quality_summary = monitoring_service.get_data_quality_summary(db, current_user.organization_id)
    schedule_summary = monitoring_service.get_schedule_monitoring(db, current_user.organization_id)

    return {
        "system_health": system_health,
        "pipeline_overview": pipeline_overview,
        "quality_summary": quality_summary,
        "schedule_summary": schedule_summary
    }


@router.get("/system-health", tags=["Monitoring"])
def get_system_health_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

) -> Dict[str, Any]:
    return monitoring_service.get_system_health(db)


@router.get("/failures", tags=["Monitoring"])
def get_pipeline_failures_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

) -> List[Dict[str, Any]]:
    return monitoring_service.get_pipeline_failures(db, current_user.organization_id)


@router.get("/performance", tags=["Monitoring"])
def get_performance_analytics_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

) -> Dict[str, Any]:
    return monitoring_service.get_performance_analytics(db, current_user.organization_id)


@router.get("/data-quality", tags=["Monitoring"])
def get_data_quality_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)

) -> Dict[str, Any]:
    return monitoring_service.get_data_quality_summary(db, current_user.organization_id)


@router.get("/schedules", tags=["Monitoring"])
def get_schedules_monitoring_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
) -> Dict[str, Any]:
    return monitoring_service.get_schedule_monitoring(db, current_user.organization_id)

