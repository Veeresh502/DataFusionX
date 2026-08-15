from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class WarehouseModel(Base):
    __tablename__ = "warehouse_models"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    organization_id = Column(Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    
    name = Column(String, nullable=False)         # e.g., "Sales Analytics", "Manufacturing Analytics"
    slug = Column(String, nullable=False, index=True)  # e.g., "sales", "manufacturing"
    domain = Column(String, nullable=False)       # e.g., "SALES", "MANUFACTURING", "HR", "FINANCE"
    description = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False)

    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    organization = relationship("Organization")
    tables = relationship("WarehouseTable", back_populates="warehouse_model", cascade="all, delete-orphan")
