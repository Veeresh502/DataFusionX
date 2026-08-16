from typing import Optional
from pydantic import BaseModel


class HealthStatus(BaseModel):
    status: str
    database: Optional[str] = "healthy"
    redis: Optional[str] = "healthy"
    celery: Optional[str] = "healthy"
    version: Optional[str] = "0.6.0"


class DatabaseHealthStatus(BaseModel):
    status: str
    database: str
