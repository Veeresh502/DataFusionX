from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class PipelineCreate(BaseModel):
    name: str = Field(..., min_length=1)
    description: Optional[str] = None
    source_id: Optional[int] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)
    destination_config: Dict[str, Any] = Field(default_factory=dict)
    dag_nodes: Optional[List[Dict[str, Any]]] = Field(default_factory=list)
    dag_edges: Optional[List[Dict[str, Any]]] = Field(default_factory=list)


class PipelineUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    source_id: Optional[int] = None
    steps: Optional[List[Dict[str, Any]]] = None
    destination_config: Optional[Dict[str, Any]] = None
    dag_nodes: Optional[List[Dict[str, Any]]] = None
    dag_edges: Optional[List[Dict[str, Any]]] = None


class PipelineOut(BaseModel):
    id: int
    organization_id: int
    name: str
    description: Optional[str] = None
    source_id: int
    steps: List[Dict[str, Any]]
    destination_config: Dict[str, Any]
    dag_nodes: Optional[List[Dict[str, Any]]] = []
    dag_edges: Optional[List[Dict[str, Any]]] = []
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class DAGValidationRequest(BaseModel):
    dag_nodes: List[Dict[str, Any]]
    dag_edges: List[Dict[str, Any]]


class DAGValidationResponse(BaseModel):
    valid: bool
    errors: List[str] = Field(default_factory=list)
    execution_order: List[str] = Field(default_factory=list)
    source_id: Optional[int] = None
    destination_config: Optional[Dict[str, Any]] = None
    steps: List[Dict[str, Any]] = Field(default_factory=list)


class PipelineExecutionOut(BaseModel):
    id: int
    pipeline_id: int
    organization_id: int
    status: str
    current_stage: Optional[str] = "PENDING"
    celery_task_id: Optional[str] = None
    retry_count: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = 0.0
    records_read: int
    records_processed: int
    records_failed: int
    records_loaded: int = 0
    trigger_type: str = "MANUAL"
    schedule_id: Optional[int] = None
    logs: List[Dict[str, Any]]
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


