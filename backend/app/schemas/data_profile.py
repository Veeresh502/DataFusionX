from datetime import datetime
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, ConfigDict


class ColumnProfile(BaseModel):
    name: str
    data_type: str
    detected_type: Optional[str] = None
    null_count: int
    non_null_count: Optional[int] = None
    null_percentage: float
    completeness_percentage: Optional[float] = None
    unique_count: int
    unique_percentage: float
    duplicate_value_count: Optional[int] = None
    
    # Numerical
    min: Optional[float] = None
    max: Optional[float] = None
    mean: Optional[float] = None
    median: Optional[float] = None
    std: Optional[float] = None
    q1: Optional[float] = None
    q3: Optional[float] = None
    iqr: Optional[float] = None
    lower_bound: Optional[float] = None
    upper_bound: Optional[float] = None
    outlier_count: Optional[int] = None
    outlier_percentage: Optional[float] = None
    outliers: Optional[List[Any]] = None
    affected_row_indices: Optional[List[int]] = None

    # Categorical
    cardinality: Optional[int] = None
    top_values: Optional[List[Dict[str, Any]]] = None

    # Date
    valid_date_count: Optional[int] = None
    invalid_date_count: Optional[int] = None
    min_date: Optional[str] = None
    max_date: Optional[str] = None
    detected_date_format: Optional[str] = None
    date_distribution: Optional[List[Dict[str, Any]]] = None

    # Format / Email
    detected_format: Optional[str] = None
    valid_format_count: Optional[int] = None
    invalid_format_count: Optional[int] = None
    format_validity_percentage: Optional[float] = None


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
    quality_issues: Optional[List[Dict[str, Any]]] = None
    findings: Optional[List[Dict[str, Any]]] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
