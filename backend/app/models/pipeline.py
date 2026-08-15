from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class Pipeline(Base):
    __tablename__ = "pipelines"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    
    source_id = Column(Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, index=True)
    steps = Column(JSON, nullable=False, default=list)  # Ordered array of transformation/validation steps
    destination_config = Column(JSON, nullable=False, default=dict)  # PostgreSQL table name, if_exists: append/replace/create
    
    # Visual DAG Graph Storage
    dag_nodes = Column(JSON, nullable=True, default=list)  # React Flow node array
    dag_edges = Column(JSON, nullable=True, default=list)  # React Flow edge array
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)

    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    organization = relationship("Organization")
    source = relationship("DataSource")
    creator = relationship("User")
    executions = relationship("PipelineExecution", back_populates="pipeline", cascade="all, delete-orphan")
    schedules = relationship("PipelineSchedule", back_populates="pipeline", cascade="all, delete-orphan")

