from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PipelineExecution(Base):
    __tablename__ = "pipeline_executions"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    status = Column(String, nullable=False, default="PENDING")  # PENDING, RUNNING, RETRYING, SUCCESS, FAILED, CANCELLED
    current_stage = Column(String, nullable=False, default="PENDING")  # PENDING, EXTRACT, TRANSFORM, VALIDATE, LOAD, COMPLETE, ERROR
    celery_task_id = Column(String, nullable=True, index=True)
    retry_count = Column(Integer, nullable=False, default=0)

    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, nullable=True, default=0.0)
    
    records_read = Column(Integer, nullable=False, default=0)
    records_processed = Column(Integer, nullable=False, default=0)
    records_failed = Column(Integer, nullable=False, default=0)
    records_loaded = Column(Integer, nullable=False, default=0)
    
    logs = Column(JSON, nullable=False, default=list)  # List of log dicts: [{"timestamp": "...", "level": "INFO", "message": "..."}]
    error = Column(Text, nullable=True)


    trigger_type = Column(String, nullable=False, default="MANUAL")  # MANUAL or SCHEDULED
    schedule_id = Column(Integer, ForeignKey("pipeline_schedules.id", ondelete="SET NULL"), nullable=True, index=True)

    pipeline = relationship("Pipeline", back_populates="executions")
    organization = relationship("Organization")
    schedule = relationship("PipelineSchedule", back_populates="executions")

