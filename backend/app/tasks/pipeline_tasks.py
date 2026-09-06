import json
import time
from datetime import datetime, timezone
from typing import Optional
import redis
from celery.exceptions import MaxRetriesExceededError
from sqlalchemy.exc import OperationalError, DatabaseError
from sqlalchemy.orm import Session

from app.core.celery_app import celery_app
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.pipeline_execution import PipelineExecution
from app.models.pipeline import Pipeline
from app.services.etl_engine import (
    extract_data,
    transform_dataframe,
    validate_dataframe,
    load_data_to_postgres,
    ETLLogger,
)


def get_redis_client():
    return redis.Redis.from_url(settings.CELERY_BROKER_URL, decode_responses=True)


def publish_execution_event(execution_id: int, event_type: str, data: dict):
    try:
        r = get_redis_client()
        message = {
            "event": event_type,
            "execution_id": execution_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **data
        }
        r.publish(f"execution:{execution_id}", json.dumps(message))
    except Exception as e:
        print(f"[Redis Event Publish Warning] Could not publish event: {e}")


def _is_validation_step(s: dict) -> bool:
    cat = str(s.get("category") or "").lower()
    tp = str(s.get("type") or s.get("node_type") or "").lower()
    rule_tp = str(s.get("rule_type") or "").lower()
    
    if cat == "validation" or cat == "val":
        return True
    if cat == "transformation":
        return False
        
    val_rules = ["not_null", "unique", "primary_key", "range", "regex"]
    return any(r in tp for r in val_rules) or any(r in rule_tp for r in val_rules)



@celery_app.task(bind=True, max_retries=3)
def execute_pipeline_task(self, execution_id: int, db: Optional[Session] = None):
    """
    Celery task orchestrating asynchronous pipeline execution.
    Delegates actual ETL logic to existing ETL engine & generic warehouse engine.
    """
    own_db = False
    if db is None:
        db = SessionLocal()
        own_db = True

    start_time = time.time()
    logger = ETLLogger()
    task_id = getattr(getattr(self, "request", None), "id", None) or "local-exec"

    try:
        execution = db.query(PipelineExecution).filter(PipelineExecution.id == execution_id).first()
        if not execution:
            return {"status": "FAILED", "error": f"Execution ID {execution_id} not found"}

        pipeline = db.query(Pipeline).filter(Pipeline.id == execution.pipeline_id).first()
        if not pipeline:
            execution.status = "FAILED"
            execution.current_stage = "ERROR"
            execution.error = f"Pipeline ID {execution.pipeline_id} not found"
            execution.completed_at = datetime.now(timezone.utc)
            db.commit()
            publish_execution_event(execution_id, "EXECUTION_FAILED", {"error": execution.error, "status": "FAILED"})
            return {"status": "FAILED", "error": execution.error}

        # Update execution to RUNNING
        execution.celery_task_id = task_id
        execution.status = "RUNNING"
        execution.current_stage = "EXTRACT"
        db.commit()

        publish_execution_event(execution_id, "EXECUTION_STARTED", {
            "status": "RUNNING",
            "current_stage": "EXTRACT",
            "celery_task_id": task_id,
        })

        source = pipeline.source
        if not source:
            raise ValueError(f"Data source ID {pipeline.source_id} not found")

        # STAGE 1: EXTRACT
        execution.current_stage = "EXTRACT"
        db.commit()
        publish_execution_event(execution_id, "STAGE_STARTED", {"stage": "EXTRACT"})
        
        t0 = time.time()
        extracted_df = extract_data(source, logger)
        t1 = time.time()
        execution.records_read = len(extracted_df)
        execution.logs = logger.logs
        db.commit()

        try:
            from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS, PIPELINE_RECORDS_READ_TOTAL
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="EXTRACT").observe(t1 - t0)
            PIPELINE_RECORDS_READ_TOTAL.inc(len(extracted_df))
        except Exception:
            pass
        
        publish_execution_event(execution_id, "PROGRESS", {
            "stage": "EXTRACT",
            "records_read": len(extracted_df),
            "logs": logger.logs
        })

        # STAGE 2: TRANSFORM
        execution.current_stage = "TRANSFORM"
        db.commit()
        publish_execution_event(execution_id, "STAGE_STARTED", {"stage": "TRANSFORM"})

        steps = pipeline.steps or []
        transform_steps = [s for s in steps if not _is_validation_step(s)]
        validation_steps = [s for s in steps if _is_validation_step(s)]

        t2 = time.time()
        try:
            transformed_df = transform_dataframe(extracted_df, transform_steps, logger)
        except Exception as tf_err:
            logger.error(f"Transformation failed: {str(tf_err)}")
            logger.info("Validation skipped because transformation failed")
            logger.info("Load skipped because transformation failed")
            execution.records_processed = 0
            execution.records_failed = 0
            execution.records_loaded = 0
            execution.status = "FAILED"
            execution.current_stage = "FAILED"
            execution.error = f"Transformation Failure: {str(tf_err)}"
            execution.completed_at = datetime.now(timezone.utc)
            duration = round(time.time() - start_time, 3)
            execution.duration_seconds = duration
            execution.logs = logger.logs
            db.commit()

            try:
                from app.core.prometheus import PIPELINE_FAILURES_TOTAL
                PIPELINE_FAILURES_TOTAL.inc()
            except Exception:
                pass

            publish_execution_event(execution_id, "EXECUTION_FAILED", {
                "status": "FAILED",
                "current_stage": "FAILED",
                "records_read": execution.records_read,
                "records_processed": 0,
                "records_failed": 0,
                "records_loaded": 0,
                "duration_seconds": execution.duration_seconds,
                "error": execution.error,
                "logs": logger.logs
            })

            return {"status": "FAILED", "execution_id": execution_id, "error": execution.error}

        t3 = time.time()

        execution.logs = logger.logs
        db.commit()

        try:
            from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="TRANSFORM").observe(t3 - t2)
        except Exception:
            pass

        publish_execution_event(execution_id, "PROGRESS", {
            "stage": "TRANSFORM",
            "records_processed": len(transformed_df),
            "logs": logger.logs
        })

        # STAGE 3: VALIDATE
        execution.current_stage = "VALIDATE"
        db.commit()
        publish_execution_event(execution_id, "STAGE_STARTED", {"stage": "VALIDATE"})

        t4 = time.time()
        valid_df, invalid_df, validation_errors = validate_dataframe(transformed_df, validation_steps, logger)
        t5 = time.time()
        execution.records_processed = len(valid_df)
        execution.records_failed = len(invalid_df)
        execution.logs = logger.logs
        db.commit()

        try:
            from app.core.prometheus import (
                PIPELINE_STAGE_DURATION_SECONDS,
                PIPELINE_RECORDS_PROCESSED_TOTAL,
                PIPELINE_VALIDATION_ERRORS_TOTAL,
                PIPELINE_INVALID_RECORDS_TOTAL
            )
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="VALIDATE").observe(t5 - t4)
            PIPELINE_RECORDS_PROCESSED_TOTAL.inc(len(valid_df))
            if validation_errors:
                PIPELINE_VALIDATION_ERRORS_TOTAL.inc(len(validation_errors))
            if len(invalid_df) > 0:
                PIPELINE_INVALID_RECORDS_TOTAL.inc(len(invalid_df))
        except Exception:
            pass

        publish_execution_event(execution_id, "PROGRESS", {
            "stage": "VALIDATE",
            "records_processed": len(valid_df),
            "records_failed": len(invalid_df),
            "logs": logger.logs
        })

        # CHECK VALIDATION FAILURE -> BLOCK LOAD & MARK EXECUTION FAILED
        if validation_errors or len(invalid_df) > 0:
            err_summary = validation_errors[0] if validation_errors else f"Validation failed with {len(invalid_df)} invalid records."
            execution.records_loaded = 0
            execution.status = "FAILED"
            execution.current_stage = "FAILED"
            execution.error = f"Validation Failure: {err_summary}"
            execution.completed_at = datetime.now(timezone.utc)
            duration = round(time.time() - start_time, 3)
            execution.duration_seconds = duration
            execution.logs = logger.logs
            db.commit()

            try:
                from app.core.prometheus import PIPELINE_FAILURES_TOTAL
                PIPELINE_FAILURES_TOTAL.inc()
            except Exception:
                pass

            publish_execution_event(execution_id, "EXECUTION_FAILED", {
                "status": "FAILED",
                "current_stage": "FAILED",
                "records_read": execution.records_read,
                "records_processed": execution.records_processed,
                "records_failed": execution.records_failed,
                "records_loaded": 0,
                "duration_seconds": execution.duration_seconds,
                "error": execution.error,
                "logs": logger.logs
            })

            return {"status": "FAILED", "execution_id": execution_id, "error": execution.error}

        # STAGE 4: LOAD
        execution.current_stage = "LOAD"
        db.commit()
        publish_execution_event(execution_id, "STAGE_STARTED", {"stage": "LOAD"})

        t6 = time.time()
        if not valid_df.empty and pipeline.destination_config:
            loaded_count = load_data_to_postgres(valid_df, pipeline.destination_config, logger, db=db)
            execution.records_loaded = loaded_count
        else:
            execution.records_loaded = 0
            logger.info("Load skipped: No valid records to write or destination omitted")
        t7 = time.time()

        try:
            from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS, PIPELINE_RECORDS_LOADED_TOTAL
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="LOAD").observe(t7 - t6)
            PIPELINE_RECORDS_LOADED_TOTAL.inc(execution.records_loaded)
        except Exception:
            pass

        execution.status = "SUCCESS"
        execution.current_stage = "COMPLETE"
        execution.completed_at = datetime.now(timezone.utc)
        duration = round(time.time() - start_time, 3)
        execution.duration_seconds = duration
        execution.logs = logger.logs
        db.commit()

        try:
            from app.core.prometheus import (
                PIPELINE_EXECUTIONS_TOTAL,
                PIPELINE_EXECUTION_DURATION_SECONDS,
                PIPELINE_THROUGHPUT
            )
            dest_type = (pipeline.destination_config or {}).get("destination_type", "POSTGRES")
            trig_type = getattr(execution, "trigger_type", "MANUAL")
            PIPELINE_EXECUTIONS_TOTAL.labels(status="SUCCESS", trigger_type=trig_type, destination_type=dest_type).inc()
            PIPELINE_EXECUTION_DURATION_SECONDS.labels(status="SUCCESS", trigger_type=trig_type).observe(duration)
            if duration > 0 and (execution.records_processed or 0) > 0:
                PIPELINE_THROUGHPUT.set(round(execution.records_processed / duration, 2))
        except Exception:
            pass

        publish_execution_event(execution_id, "EXECUTION_SUCCESS", {
            "status": "SUCCESS",
            "current_stage": "COMPLETE",
            "records_read": execution.records_read,
            "records_processed": execution.records_processed,
            "records_failed": execution.records_failed,
            "records_loaded": execution.records_loaded,
            "duration_seconds": execution.duration_seconds,
            "logs": logger.logs
        })

        return {"status": execution.status, "execution_id": execution_id}



    except (OperationalError, DatabaseError, ConnectionError) as exc:
        execution.retry_count += 1
        execution.status = "RETRYING"
        execution.logs = logger.logs
        db.commit()

        publish_execution_event(execution_id, "EXECUTION_RETRYING", {
            "status": "RETRYING",
            "retry_count": execution.retry_count,
            "max_retries": 3,
            "error": str(exc),
            "logs": logger.logs
        })

        try:
            retries = getattr(getattr(self, "request", None), "retries", 0)
            countdown = 2 ** retries
            if hasattr(self, "retry"):
                raise self.retry(exc=exc, countdown=countdown)
            else:
                raise exc
        except MaxRetriesExceededError:
            execution.status = "FAILED"
            execution.current_stage = "ERROR"
            execution.error = f"Max retries exceeded: {str(exc)}"
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration_seconds = round(time.time() - start_time, 3)
            db.commit()

            publish_execution_event(execution_id, "EXECUTION_FAILED", {
                "status": "FAILED",
                "current_stage": "ERROR",
                "error": execution.error,
                "logs": logger.logs
            })
            return {"status": "FAILED", "execution_id": execution_id}

    except Exception as exc:
        execution.status = "FAILED"
        execution.current_stage = "ERROR"
        execution.error = str(exc)
        execution.completed_at = datetime.now(timezone.utc)
        execution.duration_seconds = round(time.time() - start_time, 3)
        execution.logs = logger.logs
        db.commit()

        publish_execution_event(execution_id, "EXECUTION_FAILED", {
            "status": "FAILED",
            "current_stage": "ERROR",
            "error": str(exc),
            "logs": logger.logs
        })
        return {"status": "FAILED", "execution_id": execution_id}

    finally:
        if own_db:
            db.close()
