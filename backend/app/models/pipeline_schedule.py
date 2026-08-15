from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class PipelineSchedule(Base):
    __tablename__ = "pipeline_schedules"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    pipeline_id = Column(Integer, ForeignKey("pipelines.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)
    cron_expression = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    enabled = Column(Boolean, nullable=False, default=True, index=True)
    
    next_run_at = Column(DateTime(timezone=True), nullable=True, index=True)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    organization = relationship("Organization")
    pipeline = relationship("Pipeline", back_populates="schedules")
    creator = relationship("User")
    executions = relationship("PipelineExecution", back_populates="schedule")
