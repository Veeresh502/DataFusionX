from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class DataSource(Base):
    __tablename__ = "data_sources"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    name = Column(String, nullable=False)
    type = Column(String, nullable=False)  # CSV, EXCEL, JSON, REST_API, POSTGRESQL
    description = Column(String, nullable=True)
    
    # Configuration metadata (rows, columns, schema, sanitized preview, non-sensitive connection fields)
    configuration = Column(JSON, nullable=True)
    
    # AES-256-GCM encrypted sensitive credentials (passwords, tokens)
    encrypted_credentials = Column(Text, nullable=True)
    
    created_by = Column(Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    organization = relationship("Organization", back_populates="data_sources")
    creator = relationship("User")
