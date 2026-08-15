from datetime import datetime, date
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict


class TableColumnInfo(BaseModel):
    name: str
    type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False


class WarehouseTableSummary(BaseModel):
    table_name: str
    column_count: int
    row_count: int
    primary_keys: List[str]
    foreign_keys: List[str]


class WarehouseTableDetail(BaseModel):
    table_name: str
    columns: List[TableColumnInfo]
    primary_keys: List[str]
    foreign_keys: List[str]
    row_count: int
    sample_records: List[Dict[str, Any]]


class RevenueMetrics(BaseModel):
    total_revenue: float
    total_quantity: int
    average_order_value: float
    revenue_by_product: List[Dict[str, Any]]
    revenue_by_category: List[Dict[str, Any]]
    revenue_by_customer: List[Dict[str, Any]]
    revenue_by_city: List[Dict[str, Any]]
    revenue_by_month: List[Dict[str, Any]]
    top_products: List[Dict[str, Any]]


class WarehouseTableOut(BaseModel):
    id: int
    warehouse_model_id: int
    table_name: str
    table_type: str  # FACT or DIMENSION
    description: Optional[str] = None
    grain: Optional[str] = None
    primary_keys: List[str]
    foreign_keys: List[str]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class WarehouseModelOut(BaseModel):
    id: int
    organization_id: int
    name: str
    slug: str
    domain: str
    description: Optional[str] = None
    is_active: bool
    tables: List[WarehouseTableOut] = []
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class GenericWarehouseAnalytics(BaseModel):
    model_id: int
    model_name: str
    domain: str
    total_fact_rows: int
    total_dimension_rows: int
    fact_table_count: int
    dimension_table_count: int
    tables_summary: List[WarehouseTableSummary]
    last_updated: Optional[str] = None


class ManufacturingMetrics(BaseModel):
    total_production_batches: int
    total_units_produced: int
    total_defect_count: int
    defect_rate_percentage: float
    total_operating_hours: float
    production_by_machine: List[Dict[str, Any]]
    defects_by_plant: List[Dict[str, Any]]

