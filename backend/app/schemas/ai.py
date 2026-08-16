from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field


class AIQueryRequest(BaseModel):
    question: str = Field(..., description="Natural language question to ask against the warehouse")
    warehouse_model: Optional[str] = Field("sales", description="Warehouse model slug (e.g. sales, manufacturing) or table name")


class AIQueryResponse(BaseModel):
    question: str
    sql: str
    columns: List[str]
    rows: List[Dict[str, Any]]
    row_count: int
    explanation: str
    execution_time_ms: float
    warehouse_model: str


class AIPipelineExplainRequest(BaseModel):
    execution_id: int = Field(..., description="ID of the failed pipeline execution to analyze")


class AIPipelineExplainResponse(BaseModel):
    execution_id: int
    pipeline_id: int
    pipeline_name: str
    summary: str
    root_cause: str
    suggested_fix: str
    stage: str


class AIHealthResponse(BaseModel):
    status: str
    provider: str
    model: str
