import time
from datetime import datetime, timezone
from typing import Optional
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.db.session import SessionLocal
from app.models.pipeline_schedule import PipelineSchedule
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.schedule_service import calculate_next_run, utcnow, make_utc_aware

from app.tasks.pipeline_tasks import execute_pipeline_task


@celery_app.task(name="app.tasks.schedule_tasks.check_and_dispatch_scheduled_pipelines")
def check_and_dispatch_scheduled_pipelines(db: Optional[Session] = None):
    """
    Celery Beat periodic task running every 15 seconds.
    Reads due enabled schedules, prevents duplicate/overlapping execution,
    updates last_run_at and next_run_at, creates SCHEDULED execution records,
    and dispatches the existing execute_pipeline_task.
    """
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    dispatched_count = 0


    try:
        now = utcnow()
        # Query enabled schedules with a next_run_at set
        all_enabled = db.query(PipelineSchedule).filter(
            PipelineSchedule.enabled == True,
            PipelineSchedule.next_run_at != None
        ).all()

        due_schedules = [
            s for s in all_enabled
            if make_utc_aware(s.next_run_at) <= now
        ]


        if not due_schedules:
            return {"status": "SUCCESS", "dispatched": 0, "message": "No due schedules found"}

        for schedule in due_schedules:
            pipeline = db.query(Pipeline).filter(Pipeline.id == schedule.pipeline_id).first()
            if not pipeline or pipeline.organization_id != schedule.organization_id:
                # Pipeline deleted or unauthorized; disable schedule
                schedule.enabled = False
                schedule.next_run_at = None
                db.commit()
                continue

            # 1. OVERLAP PROTECTION: Check if active execution exists for this pipeline
            active_execution = db.query(PipelineExecution).filter(
                PipelineExecution.pipeline_id == schedule.pipeline_id,
                PipelineExecution.status.in_(["PENDING", "RUNNING", "RETRYING"])
            ).first()

            if active_execution:
                # Overlap detected! Advance next_run_at so Beat doesn't get stuck, but skip dispatch
                print(f"[Beat Overlap Protection] Pipeline #{schedule.pipeline_id} already has active execution #{active_execution.id} ({active_execution.status}). Skipping duplicate dispatch for Schedule #{schedule.id}.")
                schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone, start_dt=now)
                db.commit()
                continue

            # 2. DUPLICATE DISPATCH PROTECTION & NEXT-RUN CALCULATION
            schedule.last_run_at = now
            schedule.next_run_at = calculate_next_run(schedule.cron_expression, schedule.timezone, start_dt=now)
            
            # 3. CREATE SCHEDULED EXECUTION RECORD
            execution = PipelineExecution(
                pipeline_id=schedule.pipeline_id,
                organization_id=schedule.organization_id,
                schedule_id=schedule.id,
                trigger_type="SCHEDULED",
                status="PENDING",
                current_stage="PENDING",
                logs=[{
                    "timestamp": now.isoformat(),
                    "level": "INFO",
                    "message": f"Pipeline execution triggered by schedule '{schedule.name}' (Cron: {schedule.cron_expression}, TZ: {schedule.timezone})"
                }]
            )
            db.add(execution)
            db.commit()
            db.refresh(execution)

            # 4. DISPATCH TO EXISTING M8 CELERY EXECUTION TASK
            execute_pipeline_task.delay(execution.id)
            dispatched_count += 1
            print(f"[Beat Scheduled Dispatch] Successfully dispatched Execution #{execution.id} for Schedule '{schedule.name}' (Pipeline #{schedule.pipeline_id}).")

        return {
            "status": "SUCCESS",
            "dispatched": dispatched_count,
            "due_checked": len(due_schedules)
        }

    except Exception as e:
        db.rollback()
        print(f"[Beat Task Error] Error checking scheduled pipelines: {e}")
        return {"status": "ERROR", "error": str(e)}
    finally:
        if own_db:
            db.close()

