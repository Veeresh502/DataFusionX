from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, ConfigDict, Field


class RESTConnectionTestRequest(BaseModel):
    url: str
    method: str = "GET"
    headers: Optional[Dict[str, str]] = None
    auth_token: Optional[str] = None


class PostgresConnectionTestRequest(BaseModel):
    host: str
    port: int = 5432
    database: str
    username: str
    password: str
    schema_name: Optional[str] = "public"
    table: Optional[str] = None


class ConnectionTestResponse(BaseModel):
    success: bool
    message: str
    details: Optional[Dict[str, Any]] = None


class DataSourceCreate(BaseModel):
    name: str = Field(..., min_length=1)
    type: str = Field(..., description="CSV, EXCEL, JSON, REST_API, POSTGRESQL")
    description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    credentials: Optional[Dict[str, Any]] = None


class DataSourceOut(BaseModel):
    id: int
    organization_id: int
    name: str
    type: str
    description: Optional[str] = None
    configuration: Optional[Dict[str, Any]] = None
    created_by: Optional[int] = None
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)
