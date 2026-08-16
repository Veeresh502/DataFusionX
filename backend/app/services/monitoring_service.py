from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.models.pipeline_schedule import PipelineSchedule
from app.models.data_profile import DataProfile
from app.services.health import check_database_health, check_redis_health, check_celery_health, check_full_health


def get_system_health(db: Session) -> Dict[str, Any]:
    full_health = check_full_health(db)
    
    # Active schedules count
    active_schedules = db.query(func.count(PipelineSchedule.id)).filter(
        PipelineSchedule.enabled == True
    ).scalar() or 0

    return {
        "overall": full_health.status.upper(),
        "api": "HEALTHY",
        "database": full_health.database.upper(),
        "redis": full_health.redis.upper(),
        "celery": full_health.celery.upper(),
        "active_schedules": active_schedules,
        "version": full_health.version
    }


def get_pipeline_overview(db: Session, organization_id: int) -> Dict[str, Any]:
    # Query executions for current user's organization
    base_query = db.query(PipelineExecution).filter(
        PipelineExecution.organization_id == organization_id
    )

    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    today_query = base_query.filter(PipelineExecution.started_at >= today_start)

    total_today = today_query.count()
    success_today = today_query.filter(PipelineExecution.status == "SUCCESS").count()
    failed_today = today_query.filter(PipelineExecution.status == "FAILED").count()
    retrying_today = today_query.filter(PipelineExecution.status == "RETRYING").count()
    running_today = today_query.filter(PipelineExecution.status == "RUNNING").count()

    # Derived metrics across all executions
    stats = db.query(
        func.count(PipelineExecution.id).label("total_all"),
        func.avg(PipelineExecution.duration_seconds).label("avg_duration"),
        func.min(PipelineExecution.duration_seconds).label("min_duration"),
        func.max(PipelineExecution.duration_seconds).label("max_duration"),
        func.sum(PipelineExecution.records_read).label("total_read"),
        func.sum(PipelineExecution.records_processed).label("total_processed"),
        func.sum(PipelineExecution.records_loaded).label("total_loaded"),
        func.sum(PipelineExecution.records_failed).label("total_failed"),
    ).filter(
        PipelineExecution.organization_id == organization_id
    ).first()

    avg_dur = round(float(stats.avg_duration or 0), 2)
    min_dur = round(float(stats.min_duration or 0), 2)
    max_dur = round(float(stats.max_duration or 0), 2)
    total_processed = int(stats.total_processed or 0)
    total_read = int(stats.total_read or 0)
    total_loaded = int(stats.total_loaded or 0)
    total_failed_records = int(stats.total_failed or 0)

    # Average throughput (records/sec)
    overall_seconds = db.query(func.sum(PipelineExecution.duration_seconds)).filter(
        PipelineExecution.organization_id == organization_id,
        PipelineExecution.status == "SUCCESS"
    ).scalar() or 0

    throughput = round(total_processed / overall_seconds, 2) if overall_seconds > 0 else 0.0

    success_rate = round((success_today / total_today * 100), 1) if total_today > 0 else 100.0

    return {
        "total_executions_today": total_today,
        "successful_today": success_today,
        "failed_today": failed_today,
        "retrying_today": retrying_today,
        "running_today": running_today,
        "success_rate": success_rate,
        "average_duration_seconds": avg_dur,
        "min_duration_seconds": min_dur,
        "max_duration_seconds": max_dur,
        "total_records_read": total_read,
        "total_records_processed": total_processed,
        "total_records_loaded": total_loaded,
        "total_failed_records": total_failed_records,
        "throughput_records_per_sec": throughput,
    }


def get_pipeline_failures(db: Session, organization_id: int) -> List[Dict[str, Any]]:
    # Top failing pipelines for the organization
    failure_stats = db.query(
        Pipeline.id.label("pipeline_id"),
        Pipeline.name.label("pipeline_name"),
        func.count(PipelineExecution.id).label("total_executions"),
        func.sum(case((PipelineExecution.status == "FAILED", 1), else_=0)).label("failed_executions"),
        func.max(PipelineExecution.started_at).label("last_execution_time")
    ).join(
        PipelineExecution, Pipeline.id == PipelineExecution.pipeline_id
    ).filter(
        Pipeline.organization_id == organization_id
    ).group_by(
        Pipeline.id, Pipeline.name
    ).all()

    results = []
    for item in failure_stats:
        total = item.total_executions or 0
        failed = int(item.failed_executions or 0)
        rate = round((failed / total * 100), 1) if total > 0 else 0.0
        results.append({
            "pipeline_id": item.pipeline_id,
            "pipeline_name": item.pipeline_name,
            "total_executions": total,
            "failed_executions": failed,
            "failure_rate_pct": rate,
            "last_execution_time": item.last_execution_time.isoformat() if item.last_execution_time else None
        })

    # Sort by failure count descending
    results.sort(key=lambda x: x["failed_executions"], reverse=True)
    return results[:10]


def get_performance_analytics(db: Session, organization_id: int) -> Dict[str, Any]:
    # Slowest pipelines
    slowest_query = db.query(
        Pipeline.id.label("pipeline_id"),
        Pipeline.name.label("pipeline_name"),
        func.avg(PipelineExecution.duration_seconds).label("avg_duration"),
        func.max(PipelineExecution.duration_seconds).label("max_duration"),
        func.count(PipelineExecution.id).label("executions_count")
    ).join(
        PipelineExecution, Pipeline.id == PipelineExecution.pipeline_id
    ).filter(
        Pipeline.organization_id == organization_id
    ).group_by(
        Pipeline.id, Pipeline.name
    ).order_by(
        func.avg(PipelineExecution.duration_seconds).desc()
    ).limit(5).all()

    slowest = [
        {
            "pipeline_id": s.pipeline_id,
            "pipeline_name": s.pipeline_name,
            "avg_duration": round(float(s.avg_duration or 0), 2),
            "max_duration": round(float(s.max_duration or 0), 2),
            "executions_count": s.executions_count,
        }
        for s in slowest_query
    ]

    # Highest volume pipelines
    volume_query = db.query(
        Pipeline.id.label("pipeline_id"),
        Pipeline.name.label("pipeline_name"),
        func.sum(PipelineExecution.records_processed).label("records_processed")
    ).join(
        PipelineExecution, Pipeline.id == PipelineExecution.pipeline_id
    ).filter(
        Pipeline.organization_id == organization_id
    ).group_by(
        Pipeline.id, Pipeline.name
    ).order_by(
        func.sum(PipelineExecution.records_processed).desc()
    ).limit(5).all()

    volume = [
        {
            "pipeline_id": v.pipeline_id,
            "pipeline_name": v.pipeline_name,
            "total_records_processed": int(v.records_processed or 0)
        }
        for v in volume_query
    ]

    # Execution history timeline for charts (last 20 executions)
    timeline_query = db.query(PipelineExecution).filter(
        PipelineExecution.organization_id == organization_id
    ).order_by(PipelineExecution.started_at.desc()).limit(20).all()

    timeline = [
        {
            "execution_id": e.id,
            "pipeline_id": e.pipeline_id,
            "status": e.status,
            "duration_seconds": e.duration_seconds or 0,
            "records_processed": e.records_processed or 0,
            "records_loaded": e.records_loaded or 0,
            "started_at": e.started_at.isoformat() if e.started_at else None
        }
        for e in reversed(timeline_query)
    ]

    return {
        "slowest_pipelines": slowest,
        "highest_volume_pipelines": volume,
        "execution_timeline": timeline
    }


def get_data_quality_summary(db: Session, organization_id: int) -> Dict[str, Any]:
    # Aggregated quality stats from DataProfile
    profiles = db.query(DataProfile).filter(
        DataProfile.organization_id == organization_id
    ).all()

    if not profiles:
        return {
            "average_quality_score": 100.0,
            "total_profiles_analyzed": 0,
            "total_quality_warnings": 0,
            "total_critical_errors": 0,
            "total_invalid_records": 0
        }

    total_score = sum(p.quality_score or 100.0 for p in profiles)
    avg_score = round(total_score / len(profiles), 1)

    # Derived validation error counts from executions
    exec_stats = db.query(
        func.sum(PipelineExecution.records_failed).label("total_invalid")
    ).filter(
        PipelineExecution.organization_id == organization_id
    ).first()

    total_invalid = int(exec_stats.total_invalid or 0)

    return {
        "average_quality_score": avg_score,
        "total_profiles_analyzed": len(profiles),
        "total_quality_warnings": sum(len(p.warnings or []) for p in profiles),
        "total_critical_errors": sum(1 for p in profiles if (p.quality_score or 100) < 60),
        "total_invalid_records": total_invalid
    }


def get_schedule_monitoring(db: Session, organization_id: int) -> Dict[str, Any]:
    schedules = db.query(PipelineSchedule).filter(
        PipelineSchedule.organization_id == organization_id
    ).all()

    total_schedules = len(schedules)
    enabled_schedules = sum(1 for s in schedules if s.enabled)

    # Scheduled executions today
    now = datetime.now(timezone.utc)
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

    sched_execs = db.query(PipelineExecution).filter(
        PipelineExecution.organization_id == organization_id,
        PipelineExecution.trigger_type == "SCHEDULED",
        PipelineExecution.started_at >= today_start
    ).all()

    total_sched_today = len(sched_execs)
    successful_sched_today = sum(1 for e in sched_execs if e.status == "SUCCESS")
    failed_sched_today = sum(1 for e in sched_execs if e.status == "FAILED")

    return {
        "total_schedules": total_schedules,
        "enabled_schedules": enabled_schedules,
        "scheduled_executions_today": total_sched_today,
        "successful_scheduled_today": successful_sched_today,
        "failed_scheduled_today": failed_sched_today
    }
