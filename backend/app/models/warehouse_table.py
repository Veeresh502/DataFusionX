from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class WarehouseTable(Base):
    __tablename__ = "warehouse_tables"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    warehouse_model_id = Column(Integer, ForeignKey("warehouse_models.id", ondelete="CASCADE"), nullable=False, index=True)

    table_name = Column(String, nullable=False, index=True)  # e.g., "fact_sales", "dim_customer", "fact_production"
    table_type = Column(String, nullable=False)              # "FACT" or "DIMENSION"
    description = Column(String, nullable=True)
    grain = Column(String, nullable=True)                    # e.g., "One row per customer order line"

    primary_keys = Column(JSON, nullable=False, default=list)  # e.g., ["sale_key"]
    foreign_keys = Column(JSON, nullable=False, default=list)  # e.g., ["customer_key", "product_key"]

    created_at = Column(DateTime(timezone=True), default=utcnow, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow, server_default=func.now(), nullable=False)

    warehouse_model = relationship("WarehouseModel", back_populates="tables")
