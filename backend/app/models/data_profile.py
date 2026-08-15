from datetime import datetime, timezone
from sqlalchemy import Column, Integer, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class DataProfile(Base):
    __tablename__ = "data_profiles"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    data_source_id = Column(Integer, ForeignKey("data_sources.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    summary = Column(JSON, nullable=False)
    column_profiles = Column(JSON, nullable=False)
    quality_scores = Column(JSON, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    data_source = relationship("DataSource")
    organization = relationship("Organization")
