from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class DataQualityFinding(BaseModel):
    id: str
    column: str = Field(..., description="Target column name or 'dataset'/'schema' for dataset-wide findings")
    category: str = Field(..., description="Category of anomaly (e.g. NULL_SPIKE, DUPLICATES, NUMERIC_OUTLIER, TEXT_INCONSISTENCY, INVALID_FORMAT, SCHEMA_MISMATCH, ROW_COUNT_ANOMALY, TRANSFORMATION_LOSS, VALIDATION_FAILURES, HISTORICAL_CHANGE)")
    severity: str = Field("WARNING", description="Severity level: INFO, WARNING, or CRITICAL")
    finding: str = Field(..., description="Short finding summary")
    evidence: List[str] = Field(default_factory=list, description="Evidence snippets or metrics")
    metric: Dict[str, Any] = Field(default_factory=dict, description="Deterministic metric dictionary")
    penalty: float = Field(0.0, description="Deduction penalty points applied for this finding")
    explanation: str = Field(..., description="Detailed AI/deterministic explanation")
    recommendation: str = Field(..., description="Recommended action for user decision")
    suggested_pipeline_prompt: Optional[str] = Field(None, description="Prompt for M12 AI Pipeline Copilot if user clicks Create Suggested Pipeline")


class QualityScoreBreakdown(BaseModel):
    score: float = Field(..., description="Deterministic quality score out of 100")
    quality_score: Optional[float] = Field(None, description="Alias for score")
    max_score: float = Field(100.0, description="Maximum possible score")
    status: str = Field("GOOD", description="Status label: EXCELLENT, GOOD, POOR")
    overall_severity: str = Field("INFO", description="Overall severity: INFO, WARNING, CRITICAL")
    completeness: Optional[float] = None
    uniqueness: Optional[float] = None
    validity: Optional[float] = None
    components: Dict[str, Any] = Field(default_factory=dict, description="Component metrics, weights, contributions and penalties")
    breakdown: Dict[str, Any] = Field(default_factory=dict, description="Deduction breakdown")


class HistoricalComparisonItem(BaseModel):
    metric_name: str
    current_value: Any
    previous_value: Any
    change_description: str
    has_history: bool = True


class DataQualityAnalysisResponse(BaseModel):
    source_id: int
    source_name: str
    source_type: str
    target_warehouse_model: str = "generic"
    row_count: int
    column_count: int
    quality_score: QualityScoreBreakdown
    summary_counts: Dict[str, int] = Field(default_factory=dict)
    findings: List[DataQualityFinding] = Field(default_factory=list)
    quality_issues: List[Dict[str, Any]] = Field(default_factory=list)
    column_profiles: List[Dict[str, Any]] = Field(default_factory=list)
    historical_comparison: List[HistoricalComparisonItem] = Field(default_factory=list)
    ai_explanation_available: bool = True
    ai_summary: str = Field(..., description="Overall AI executive summary of dataset health")


class ExecutionQualityAnalysisResponse(BaseModel):
    execution_id: int
    pipeline_id: int
    pipeline_name: str
    status: str
    records_read: int
    records_processed: int
    records_loaded: int
    records_failed: int
    loss_percentage: float
    validation_failures: List[Dict[str, Any]] = Field(default_factory=list)
    findings: List[DataQualityFinding] = Field(default_factory=list)
    ai_explanation: str
