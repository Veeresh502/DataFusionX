from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, ConfigDict


class ScheduleCreate(BaseModel):
    name: str
    pipeline_id: int
    cron_expression: str
    timezone: str = "UTC"
    enabled: bool = True


class ScheduleUpdate(BaseModel):
    name: Optional[str] = None
    cron_expression: Optional[str] = None
    timezone: Optional[str] = None
    enabled: Optional[bool] = None


class ScheduleOut(BaseModel):
    id: int
    organization_id: int
    pipeline_id: int
    name: str
    cron_expression: str
    timezone: str
    enabled: bool
    next_run_at: Optional[datetime] = None
    last_run_at: Optional[datetime] = None
    created_at: datetime
    updated_at: datetime
    pipeline_name: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CronValidationRequest(BaseModel):
    cron_expression: str
    timezone: str = "UTC"


class CronValidationResponse(BaseModel):
    valid: bool
    cron_expression: str
    timezone: str
    next_run_at: Optional[datetime] = None
    error: Optional[str] = None
