from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict


class ColumnProfile(BaseModel):
    name: str
    data_type: str
    null_count: int
    null_percentage: float
    unique_count: int
    unique_percentage: float
    
    # Numerical
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    outlier_count: Optional[int] = None
    outliers: Optional[List[float]] = None

    # Categorical
    cardinality: Optional[int] = None
    top_values: Optional[List[Dict[str, Any]]] = None

    # Date
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    date_distribution: Optional[List[Dict[str, Any]]] = None


class ProfileSummary(BaseModel):
    row_count: int
    column_count: int
    duplicate_rows: int
    memory_bytes: int


class QualityScores(BaseModel):
    completeness: float
    uniqueness: float
    validity: float
    overall: float


class DataProfileOut(BaseModel):
    id: int
    data_source_id: int
    organization_id: int
    summary: Dict[str, Any]
    column_profiles: List[Dict[str, Any]]
    quality_scores: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
