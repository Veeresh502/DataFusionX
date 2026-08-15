from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.api.deps import get_current_user
from app.models.user import User
from app.schemas.schedule import (
    ScheduleCreate,
    ScheduleUpdate,
    ScheduleOut,
    CronValidationRequest,
    CronValidationResponse,
)
from app.schemas.pipeline import PipelineExecutionOut
from app.services import schedule_service

router = APIRouter()


@router.post("", response_model=ScheduleOut, status_code=status.HTTP_201_CREATED)
def create_schedule_endpoint(
    payload: ScheduleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    Creates a new pipeline execution schedule for the current user's organization.
    Validates cron expression, timezone, and pipeline ownership.
    """
    try:
        schedule = schedule_service.create_schedule(
            db=db,
            organization_id=current_user.organization_id,
            user_id=current_user.id,
            pipeline_id=payload.pipeline_id,
            name=payload.name,
            cron_expression=payload.cron_expression,
            tz_str=payload.timezone,
            enabled=payload.enabled,
        )
        res = ScheduleOut.model_validate(schedule)
        if schedule.pipeline:
            res.pipeline_name = schedule.pipeline.name
        return res
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("", response_model=List[ScheduleOut])
def get_schedules_endpoint(
    pipeline_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Lists all pipeline schedules belonging to the user's organization."""
    schedules = schedule_service.get_schedules(
        db=db,
        organization_id=current_user.organization_id,
        pipeline_id=pipeline_id,
    )
    result = []
    for s in schedules:
        out = ScheduleOut.model_validate(s)
        if s.pipeline:
            out.pipeline_name = s.pipeline.name
        result.append(out)
    return result


@router.post("/validate-cron", response_model=CronValidationResponse)
def validate_cron_endpoint(
    payload: CronValidationRequest,
    current_user: User = Depends(get_current_user),
):
    """Validates a cron expression and calculates the next run timestamp in the target timezone."""
    is_valid = schedule_service.validate_cron_expression(payload.cron_expression)
    if not is_valid:
        return CronValidationResponse(
            valid=False,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            error="Invalid cron expression. Expected 5 fields (e.g. '*/5 * * * *', '0 9 * * *')."
        )

    is_tz_valid = schedule_service.validate_timezone_str(payload.timezone)
    if not is_tz_valid:
        return CronValidationResponse(
            valid=False,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            error=f"Invalid timezone: '{payload.timezone}'. Must be valid IANA timezone (e.g. 'Asia/Kolkata', 'UTC')."
        )

    try:
        next_run = schedule_service.calculate_next_run(payload.cron_expression, payload.timezone)
        return CronValidationResponse(
            valid=True,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            next_run_at=next_run
        )
    except Exception as e:
        return CronValidationResponse(
            valid=False,
            cron_expression=payload.cron_expression,
            timezone=payload.timezone,
            error=str(e)
        )


@router.get("/{schedule_id}", response_model=ScheduleOut)
def get_schedule_by_id_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Retrieves a single schedule by ID (organization isolated)."""
    try:
        schedule = schedule_service.get_schedule_by_id(db, schedule_id, current_user.organization_id)
        out = ScheduleOut.model_validate(schedule)
        if schedule.pipeline:
            out.pipeline_name = schedule.pipeline.name
        return out
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.put("/{schedule_id}", response_model=ScheduleOut)
def update_schedule_endpoint(
    schedule_id: int,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Updates an existing schedule and recalculates next_run_at."""
    try:
        data = payload.model_dump(exclude_unset=True)
        updated = schedule_service.update_schedule(
            db=db,
            schedule_id=schedule_id,
            organization_id=current_user.organization_id,
            data=data,
        )
        out = ScheduleOut.model_validate(updated)
        if updated.pipeline:
            out.pipeline_name = updated.pipeline.name
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{schedule_id}/enable", response_model=ScheduleOut)
def enable_schedule_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Enables a schedule and calculates next valid run."""
    try:
        updated = schedule_service.toggle_schedule(db, schedule_id, current_user.organization_id, True)
        out = ScheduleOut.model_validate(updated)
        if updated.pipeline:
            out.pipeline_name = updated.pipeline.name
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.patch("/{schedule_id}/disable", response_model=ScheduleOut)
def disable_schedule_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Disables a schedule to prevent future automatic executions."""
    try:
        updated = schedule_service.toggle_schedule(db, schedule_id, current_user.organization_id, False)
        out = ScheduleOut.model_validate(updated)
        if updated.pipeline:
            out.pipeline_name = updated.pipeline.name
        return out
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.delete("/{schedule_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_schedule_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Deletes a schedule."""
    try:
        schedule_service.delete_schedule(db, schedule_id, current_user.organization_id)
        return None
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{schedule_id}/executions", response_model=List[PipelineExecutionOut])
def get_schedule_executions_endpoint(
    schedule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Gets execution history triggered by this schedule."""
    try:
        executions = schedule_service.get_schedule_executions(db, schedule_id, current_user.organization_id)
        return executions
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
