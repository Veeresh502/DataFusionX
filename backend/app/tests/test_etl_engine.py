import io
import pytest
import pandas as pd
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.core.security import get_password_hash, create_access_token
from app.services.etl_engine import (
    ETLLogger,
    transform_dataframe,
    validate_dataframe,
    run_pipeline,
)


@pytest.fixture
def etl_setup(db: Session):
    org = Organization(name="ETL Test Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="ETL Engineer",
        email="etlengineer@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return user, org, token


def test_transformations_duplicate_null_normalization():
    logger = ETLLogger()
    df = pd.DataFrame({
        "name": ["  Alice  ", "  alice  ", None, "Bob"],
        "age": [25, 25, 30, None],
        "city": ["NYC", "NYC", "LA", "SF"]
    })

    steps = [
        {"type": "trim_text", "columns": ["name"]},
        {"type": "normalize_text", "mode": "lower", "columns": ["name"]},
        {"type": "remove_duplicates", "subset": ["name", "age"]},
        {"type": "fill_null", "columns": ["name"], "fill_value": "unknown"},
        {"type": "drop_null", "columns": ["age"]},
    ]

    res_df = transform_dataframe(df, steps, logger)

    assert len(res_df) == 2  # 'alice' duplicated & dropped, age null dropped
    assert "alice" in res_df["name"].values
    assert "unknown" in res_df["name"].values



def test_calculated_derived_columns():
    logger = ETLLogger()
    df = pd.DataFrame({
        "quantity": [2, 5, 10],
        "unit_price": [100.0, 50.0, 20.0],
        "discount": [10.0, 0.0, 5.0]
    })

    steps = [
        {
            "type": "calculate_column",
            "target_column": "revenue",
            "formula": "quantity * unit_price - discount"
        }
    ]

    res_df = transform_dataframe(df, steps, logger)

    assert "revenue" in res_df.columns
    assert res_df["revenue"].tolist() == [190.0, 250.0, 195.0]


def test_record_validations():
    logger = ETLLogger()
    df = pd.DataFrame({
        "user_id": [1, 2, 2, 3],
        "email": ["valid@test.com", "bad_email", "valid2@test.com", None],
        "age": [25, 150, 30, 40]
    })

    rules = [
        {"rule_type": "PRIMARY_KEY", "column": "user_id"},
        {"rule_type": "NOT_NULL", "column": "email"},
        {"rule_type": "REGEX", "column": "email", "pattern": r"^[^@]+@[^@]+\.[^@]+$"},
        {"rule_type": "RANGE", "column": "age", "min_val": 0, "max_val": 120},
    ]

    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 1  # Only row 0 passes all rules
    assert len(invalid_df) == 3
    assert len(errors) >= 3


def test_empty_dataset_handling():
    logger = ETLLogger()
    df = pd.DataFrame(columns=["col1", "col2"])

    steps = [{"type": "remove_duplicates"}, {"type": "trim_text"}]
    res_df = transform_dataframe(df, steps, logger)

    assert len(res_df) == 0


def test_full_pipeline_csv_to_postgres_execution(client: TestClient, etl_setup, db: Session):
    user, org, token = etl_setup

    # 1. Ingest CSV Source
    csv_content = b"item,quantity,unit_price,discount\nWidget A,10,15.5,5.0\nWidget B,4,50.0,0.0\nWidget A,10,15.5,5.0"
    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("orders.csv", io.BytesIO(csv_content), "text/csv")},
        data={"name": "Raw Sales Orders"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # 2. Create ETL Pipeline Configuration
    pipeline_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Sales Order ETL",
            "description": "Calculates revenue and loads to PostgreSQL target_orders",
            "source_id": source_id,
            "steps": [
                {"type": "remove_duplicates"},
                {"type": "trim_text", "columns": ["item"]},
                {
                    "type": "calculate_column",
                    "target_column": "revenue",
                    "formula": "quantity * unit_price - discount"
                },
                {"category": "validation", "rule_type": "NOT_NULL", "column": "item"},
                {"category": "validation", "rule_type": "RANGE", "column": "revenue", "min_val": 0}
            ],
            "destination_config": {
                "table_name": "target_sales_orders",
                "if_exists": "replace"
            }
        }
    )
    assert pipeline_res.status_code == 201
    pipeline_id = pipeline_res.json()["id"]

    # 3. Trigger Pipeline Run synchronously via POST /api/pipelines/{id}/run
    run_res = client.post(
        f"/api/pipelines/{pipeline_id}/run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert run_res.status_code == 200
    exec_data = run_res.json()

    assert exec_data["status"] == "SUCCESS"
    assert exec_data["records_read"] == 3
    assert exec_data["records_processed"] == 2  # 1 duplicate removed
    assert len(exec_data["logs"]) >= 6

    # Verify logs contain required milestone markers
    log_messages = [l["message"] for l in exec_data["logs"]]
    assert any("Extract started" in m for m in log_messages)
    assert any("Records extracted" in m for m in log_messages)
    assert any("Transformation started" in m for m in log_messages)
    assert any("Validation complete" in m for m in log_messages)
    assert any("Load completed" in m for m in log_messages)


def test_failed_pipeline_execution(client: TestClient, etl_setup):
    user, org, token = etl_setup

    # Create pipeline with invalid source ID
    pipeline_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Broken Pipeline",
            "source_id": 999999,  # Non-existent source
            "steps": [],
            "destination_config": {"table_name": "broken_table"}
        }
    )
    pipeline_id = pipeline_res.json()["id"]

    run_res = client.post(
        f"/api/pipelines/{pipeline_id}/run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert run_res.status_code == 200
    exec_data = run_res.json()

    assert exec_data["status"] == "FAILED"
    assert exec_data["error"] is not None
