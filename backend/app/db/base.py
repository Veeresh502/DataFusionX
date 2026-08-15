from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass

# Import all models here so Alembic registers them
from app.models.organization import Organization
from app.models.user import User
from app.models.project import Project
from app.models.data_source import DataSource
from app.models.data_profile import DataProfile
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.models.pipeline_schedule import PipelineSchedule
from app.models.warehouse import DimCustomer, DimProduct, DimDate, DimLocation, FactSales






