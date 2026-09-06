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
    intent: Optional[Dict[str, Any]] = None



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


# --- M12 AI PIPELINE COPILOT SCHEMAS ---
class AIPipelineGenerateRequest(BaseModel):
    source_id: int = Field(..., description="ID of the dataset/data source to build a pipeline for")
    user_prompt: str = Field(..., description="Natural language ETL pipeline requirement")


class ProposalErrorItem(BaseModel):
    type: str
    value: Optional[str] = None
    message: str


class AIPipelineProposalResponse(BaseModel):
    proposed_name: str
    source_id: int
    source_name: str
    source_type: str
    detected_columns: List[str]
    steps: List[Dict[str, Any]]
    destination_config: Dict[str, Any]
    dag_nodes: List[Dict[str, Any]]
    dag_edges: List[Dict[str, Any]]
    explanation: str
    step_reasons: List[Dict[str, str]]
    warnings: List[str] = []
    errors: List[ProposalErrorItem] = []
    requested_operations: List[str] = []
    resolved_operations: List[str] = []
    unsupported_operations: List[str] = []
    status: str = "VALID"  # "VALID", "INVALID", "INCOMPLETE", "WARNING"
    can_approve: bool = True
    confidence_score: float = 0.95
    is_valid: bool = True


