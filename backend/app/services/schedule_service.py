import zoneinfo
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from croniter import croniter
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.models.pipeline_schedule import PipelineSchedule
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution


def utcnow():
    return datetime.now(timezone.utc)


def make_utc_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """Ensures datetime object is timezone-aware in UTC."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)



def validate_cron_expression(cron_expr: str) -> bool:
    """Validates if string is a valid standard 5-part cron expression."""
    if not cron_expr or not isinstance(cron_expr, str):
        return False
    return croniter.is_valid(cron_expr.strip())


def validate_timezone_str(tz_str: str) -> bool:
    """Validates if string is a valid timezone identifier recognized by IANA/zoneinfo."""
    if not tz_str or not isinstance(tz_str, str):
        return False
    try:
        zoneinfo.ZoneInfo(tz_str.strip())
        return True
    except Exception:
        return False


def calculate_next_run(
    cron_expr: str,
    tz_str: str = "UTC",
    start_dt: Optional[datetime] = None
) -> datetime:
    """
    Calculates the next scheduled run datetime given a cron expression and target timezone.
    Returns a timezone-aware UTC datetime for database storage.
    """
    if not validate_cron_expression(cron_expr):
        raise ValueError(f"Invalid cron expression: '{cron_expr}'")

    tz_name = tz_str.strip() if validate_timezone_str(tz_str) else "UTC"
    tz = zoneinfo.ZoneInfo(tz_name)

    base_utc = start_dt if start_dt is not None else utcnow()
    # Convert UTC base time to target local timezone
    local_base = base_utc.astimezone(tz)
    
    iter_obj = croniter(cron_expr.strip(), local_base)
    next_local = iter_obj.get_next(datetime)
    
    # Convert back to UTC for consistent persistence
    return next_local.astimezone(timezone.utc)


# --- MULTI-TENANT CRUD OPERATIONS ---

def create_schedule(
    db: Session,
    organization_id: int,
    user_id: int,
    pipeline_id: int,
    name: str,
    cron_expression: str,
    tz_str: str = "UTC",
    enabled: bool = True,
) -> PipelineSchedule:
    """
    Creates a new pipeline schedule after validating pipeline ownership, cron format, and timezone.
    """
    # 1. Validate Pipeline Ownership
    pipeline = db.query(Pipeline).filter(
        Pipeline.id == pipeline_id,
        Pipeline.organization_id == organization_id
    ).first()
    if not pipeline:
        raise ValueError(f"Pipeline ID {pipeline_id} not found for this organization")

    # 2. Validate Cron Expression
    cron_clean = cron_expression.strip()
    if not validate_cron_expression(cron_clean):
        raise ValueError(f"Invalid cron expression: '{cron_expression}'. Must be standard 5-part cron (e.g. '*/5 * * * *', '0 9 * * *').")

    # 3. Validate Timezone
    tz_clean = tz_str.strip() if tz_str else "UTC"
    if not validate_timezone_str(tz_clean):
        raise ValueError(f"Invalid timezone: '{tz_str}'. Must be a valid IANA timezone (e.g. 'Asia/Kolkata', 'America/New_York', 'UTC').")

    # 4. Calculate Initial Next Run
    next_run = calculate_next_run(cron_clean, tz_clean)

    schedule = PipelineSchedule(
        organization_id=organization_id,
        pipeline_id=pipeline_id,
        name=name.strip(),
        cron_expression=cron_clean,
        timezone=tz_clean,
        enabled=enabled,
        next_run_at=next_run if enabled else None,
        created_by=user_id,
    )
    db.add(schedule)
    db.commit()
    db.refresh(schedule)
    return schedule


def get_schedules(
    db: Session,
    organization_id: int,
    pipeline_id: Optional[int] = None
) -> List[PipelineSchedule]:
    """Retrieves all schedules belonging to the organization."""
    query = db.query(PipelineSchedule).filter(PipelineSchedule.organization_id == organization_id)
    if pipeline_id:
        query = query.filter(PipelineSchedule.pipeline_id == pipeline_id)
    return query.order_by(PipelineSchedule.created_at.desc()).all()


def get_schedule_by_id(
    db: Session,
    schedule_id: int,
    organization_id: int
) -> PipelineSchedule:
    """Retrieves a single schedule by ID ensuring organization isolation."""
    schedule = db.query(PipelineSchedule).filter(
        PipelineSchedule.id == schedule_id,
        PipelineSchedule.organization_id == organization_id
    ).first()
    if not schedule:
        raise ValueError(f"Schedule ID {schedule_id} not found for organization")
    return schedule


def update_schedule(
    db: Session,
    schedule_id: int,
    organization_id: int,
    data: Dict[str, Any]
) -> PipelineSchedule:
    """Updates an existing schedule and recalculates next_run_at."""
    schedule = get_schedule_by_id(db, schedule_id, organization_id)

    if "name" in data and data["name"]:
        schedule.name = str(data["name"]).strip()

    if "cron_expression" in data and data["cron_expression"]:
        cron_clean = str(data["cron_expression"]).strip()
        if not validate_cron_expression(cron_clean):
            raise ValueError(f"Invalid cron expression: '{cron_clean}'")
        schedule.cron_expression = cron_clean

    if "timezone" in data and data["timezone"]:
        tz_clean = str(data["timezone"]).strip()
        if not validate_timezone_str(tz_clean):
            raise ValueError(f"Invalid timezone: '{tz_clean}'")
        schedule.timezone = tz_clean

    if "enabled" in data and data["enabled"] is not None:
        schedule.enabled = bool(data["enabled"])

    # Recalculate next_run_at if schedule is enabled
    if schedule.enabled:
        schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone)
    else:
        schedule.next_run_at = None

    db.commit()
    db.refresh(schedule)
    return schedule


def toggle_schedule(
    db: Session,
    schedule_id: int,
    organization_id: int,
    enabled: bool
) -> PipelineSchedule:
    """Enables or disables a schedule."""
    schedule = get_schedule_by_id(db, schedule_id, organization_id)
    schedule.enabled = enabled
    if enabled:
        schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone)
    else:
        schedule.next_run_at = None

    db.commit()
    db.refresh(schedule)
    return schedule


def delete_schedule(
    db: Session,
    schedule_id: int,
    organization_id: int
) -> bool:
    """Deletes a schedule."""
    schedule = get_schedule_by_id(db, schedule_id, organization_id)
    db.delete(schedule)
    db.commit()
    return True


def get_schedule_executions(
    db: Session,
    schedule_id: int,
    organization_id: int
) -> List[PipelineExecution]:
    """Returns execution history for a given schedule."""
    # Ensure schedule belongs to organization
    get_schedule_by_id(db, schedule_id, organization_id)
    return db.query(PipelineExecution).filter(
        PipelineExecution.schedule_id == schedule_id,
        PipelineExecution.organization_id == organization_id
    ).order_by(PipelineExecution.started_at.desc()).all()
