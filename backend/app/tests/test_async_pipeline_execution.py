import json
import pytest
import pandas as pd
from sqlalchemy.orm import Session
from fastapi.testclient import TestClient

from app.models.organization import Organization
from app.models.user import User
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.models.warehouse import FactSales, DimCustomer, DimProduct, DimLocation, DimDate, FactProduction, DimMachine, DimPlant
from app.services.warehouse import clear_warehouse_sales_data, clear_warehouse_manufacturing_data
from app.tasks.pipeline_tasks import execute_pipeline_task, publish_execution_event


@pytest.fixture
def clean_async_db(db: Session):
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)
    yield db
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)


def get_or_create_test_org_and_user(db: Session, name="Async Test Org"):
    org = db.query(Organization).filter(Organization.name == name).first()
    if not org:
        org = Organization(name=name)
        db.add(org)
        db.commit()
        db.refresh(org)

    user = db.query(User).filter(User.organization_id == org.id).first()
    if not user:
        user = User(
            email=f"user_{org.id}@test.com",
            password_hash="hashed_password",
            name="Async Test User",
            role="ADMIN",
            organization_id=org.id,
        )

        db.add(user)
        db.commit()
        db.refresh(user)

    return org, user


def test_1_successful_sales_pipeline(clean_async_db: Session):
    """TEST 1 — Asynchronous execution of Sales Analytics pipeline updates fact_sales and dimensions."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    sales_records = [
        {
            "order_id": "ORD-ASYNC-1",
            "order_date": "2026-08-15",
            "customer_id": "C-ASYNC-1",
            "customer_name": "Async Customer 1",
            "city": "Seattle",
            "product_id": "P-ASYNC-1",
            "product_name": "Cloud Server Unit",
            "category": "Infrastructure",
            "quantity": 3,
            "unit_price": 1000.0,
            "discount": 100.0,
            "revenue": 2900.0,
        }
    ]

    ds = DataSource(
        organization_id=org.id,
        name="Sales Async Source",
        type="CSV",
        configuration={"records": sales_records, "row_count": 1}
    )
    clean_async_db.add(ds)
    clean_async_db.commit()
    clean_async_db.refresh(ds)

    pipeline = Pipeline(
        organization_id=org.id,
        name="Sales Async Pipeline",
        source_id=ds.id,
        steps=[
            {"category": "transformation", "type": "remove_duplicates", "columns": ["order_id"]},
        ],
        destination_config={
            "destination_type": "WAREHOUSE",
            "warehouse_model_slug": "sales",
            "table_name": "sales",
            "if_exists": "append"
        }
    )
    clean_async_db.add(pipeline)
    clean_async_db.commit()
    clean_async_db.refresh(pipeline)

    execution = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=org.id,
        status="PENDING",
        current_stage="PENDING",
        logs=[]
    )
    clean_async_db.add(execution)
    clean_async_db.commit()
    clean_async_db.refresh(execution)

    # Execute task
    res = execute_pipeline_task(execution.id, db=clean_async_db)

    assert res["status"] == "SUCCESS"

    clean_async_db.refresh(execution)
    assert execution.status == "SUCCESS"
    assert execution.current_stage == "COMPLETE"
    assert execution.records_read == 1
    assert execution.records_loaded == 1

    assert clean_async_db.query(FactSales).count() == 1
    assert clean_async_db.query(DimCustomer).count() == 1
    assert clean_async_db.query(DimProduct).count() == 1


def test_2_successful_manufacturing_pipeline(clean_async_db: Session):
    """TEST 2 — Asynchronous execution of Manufacturing Analytics pipeline updates fact_production."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    mfg_records = [
        {
            "production_id": "PR-ASYNC-100",
            "production_date": "2026-08-15",
            "machine_id": "M-ASYNC-1",
            "machine_name": "Robotic Press",
            "plant_id": "PL-ASYNC-1",
            "plant_name": "Seattle Factory",
            "units_produced": 1500,
            "defect_count": 12,
            "operating_hours": 8.0,
        }
    ]

    ds = DataSource(
        organization_id=org.id,
        name="Mfg Async Source",
        type="CSV",
        configuration={"records": mfg_records, "row_count": 1}
    )
    clean_async_db.add(ds)
    clean_async_db.commit()
    clean_async_db.refresh(ds)

    pipeline = Pipeline(
        organization_id=org.id,
        name="Mfg Async Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={
            "destination_type": "WAREHOUSE",
            "warehouse_model_slug": "manufacturing",
            "table_name": "manufacturing",
            "if_exists": "append"
        }
    )
    clean_async_db.add(pipeline)
    clean_async_db.commit()
    clean_async_db.refresh(pipeline)

    execution = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=org.id,
        status="PENDING",
        current_stage="PENDING",
        logs=[]
    )
    clean_async_db.add(execution)
    clean_async_db.commit()
    clean_async_db.refresh(execution)

    res = execute_pipeline_task(execution.id, db=clean_async_db)
    assert res["status"] == "SUCCESS"

    clean_async_db.refresh(execution)
    assert execution.status == "SUCCESS"
    assert execution.records_loaded == 1
    assert clean_async_db.query(FactProduction).count() == 1
    assert clean_async_db.query(FactSales).count() == 0  # Sales tables untouched


def test_3_api_responsiveness(client: TestClient, clean_async_db: Session):
    """TEST 3 — POST /api/pipelines/{id}/run returns HTTP 200/201 response with status PENDING/RUNNING/SUCCESS."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    # Login to get JWT token
    from app.core.security import create_access_token
    token = create_access_token(subject=user.id)
    headers = {"Authorization": f"Bearer {token}"}

    ds = DataSource(
        organization_id=org.id,
        name="API Test Source",
        type="CSV",
        configuration={"records": [{"a": 1}], "row_count": 1}
    )
    clean_async_db.add(ds)
    clean_async_db.commit()

    pipeline = Pipeline(
        organization_id=org.id,
        name="API Test Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "api_test_out"}
    )
    clean_async_db.add(pipeline)
    clean_async_db.commit()

    res = client.post(f"/api/pipelines/{pipeline.id}/run", headers=headers)
    assert res.status_code in [200, 201]
    data = res.json()
    assert "id" in data
    assert data["status"] in ["PENDING", "RUNNING", "SUCCESS"]
    assert data["pipeline_id"] == pipeline.id


def test_7_deterministic_failure(clean_async_db: Session):
    """TEST 7 — Pipeline with invalid data source sets status FAILED and does not retry endlessly."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    pipeline = Pipeline(
        organization_id=org.id,
        name="Fail Pipeline",
        source_id=99999,  # Non-existent data source ID
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "fail_out"}
    )
    clean_async_db.add(pipeline)
    clean_async_db.commit()

    execution = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=org.id,
        status="PENDING",
        current_stage="PENDING",
        logs=[]
    )
    clean_async_db.add(execution)
    clean_async_db.commit()

    res = execute_pipeline_task(execution.id, db=clean_async_db)
    assert res["status"] == "FAILED"

    clean_async_db.refresh(execution)
    assert execution.status == "FAILED"
    assert execution.current_stage == "ERROR"
    assert execution.error is not None
    assert execution.retry_count == 0  # No infinite retry loop



def test_9_multiple_concurrent_executions(clean_async_db: Session):
    """TEST 9 — Multiple executions (Sales vs Manufacturing) maintain isolated logs and status."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    ds_sales = DataSource(organization_id=org.id, name="Sales DS", type="CSV", configuration={"records": [{"order_id": "O1"}], "row_count": 1})
    ds_mfg = DataSource(organization_id=org.id, name="Mfg DS", type="CSV", configuration={"records": [{"production_id": "P1"}], "row_count": 1})
    clean_async_db.add_all([ds_sales, ds_mfg])
    clean_async_db.commit()

    pipe_sales = Pipeline(organization_id=org.id, name="Pipe Sales", source_id=ds_sales.id, steps=[], destination_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "sales"})
    pipe_mfg = Pipeline(organization_id=org.id, name="Pipe Mfg", source_id=ds_mfg.id, steps=[], destination_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "manufacturing"})
    clean_async_db.add_all([pipe_sales, pipe_mfg])
    clean_async_db.commit()

    exec_sales = PipelineExecution(pipeline_id=pipe_sales.id, organization_id=org.id, status="PENDING", logs=[])
    exec_mfg = PipelineExecution(pipeline_id=pipe_mfg.id, organization_id=org.id, status="PENDING", logs=[])
    clean_async_db.add_all([exec_sales, exec_mfg])
    clean_async_db.commit()

    execute_pipeline_task(exec_sales.id, db=clean_async_db)
    execute_pipeline_task(exec_mfg.id, db=clean_async_db)

    clean_async_db.refresh(exec_sales)
    clean_async_db.refresh(exec_mfg)

    assert exec_sales.status == "SUCCESS"
    assert exec_mfg.status == "SUCCESS"
    assert exec_sales.id != exec_mfg.id
    assert len(exec_sales.logs) > 0
    assert len(exec_mfg.logs) > 0


def test_10_flat_postgresql_regression(clean_async_db: Session):
    """TEST 10 — Flat PostgreSQL table destination still works cleanly."""
    org, user = get_or_create_test_org_and_user(clean_async_db)

    ds = DataSource(organization_id=org.id, name="Flat Source", type="CSV", configuration={"records": [{"name": "Item A", "val": 100}], "row_count": 1})
    clean_async_db.add(ds)
    clean_async_db.commit()

    pipeline = Pipeline(
        organization_id=org.id,
        name="Flat Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "flat_output_m8"}
    )
    clean_async_db.add(pipeline)
    clean_async_db.commit()

    execution = PipelineExecution(pipeline_id=pipeline.id, organization_id=org.id, status="PENDING", logs=[])
    clean_async_db.add(execution)
    clean_async_db.commit()

    res = execute_pipeline_task(execution.id, db=clean_async_db)
    assert res["status"] == "SUCCESS"

    clean_async_db.refresh(execution)
    assert execution.records_loaded == 1


def test_12_multi_tenant_security(client: TestClient, clean_async_db: Session):
    """TEST 12 — User from Organization A cannot access Organization B's executions."""
    org_a, user_a = get_or_create_test_org_and_user(clean_async_db, name="Org A")
    org_b, user_b = get_or_create_test_org_and_user(clean_async_db, name="Org B")

    from app.core.security import create_access_token
    token_a = create_access_token(subject=user_a.id)
    headers_a = {"Authorization": f"Bearer {token_a}"}

    ds_b = DataSource(organization_id=org_b.id, name="DS B", type="CSV", configuration={"records": []})
    clean_async_db.add(ds_b)
    clean_async_db.commit()

    pipe_b = Pipeline(organization_id=org_b.id, name="Pipe B", source_id=ds_b.id, steps=[], destination_config={})
    clean_async_db.add(pipe_b)
    clean_async_db.commit()

    exec_b = PipelineExecution(pipeline_id=pipe_b.id, organization_id=org_b.id, status="PENDING", logs=[])
    clean_async_db.add(exec_b)
    clean_async_db.commit()

    # User A tries to run Org B's pipeline
    res = client.post(f"/api/pipelines/{pipe_b.id}/run", headers=headers_a)
    assert res.status_code in [403, 404]

    # User A tries to get Org B's execution details
    res_exec = client.get(f"/api/pipelines/executions/{exec_b.id}", headers=headers_a)
    assert res_exec.status_code in [403, 404]
