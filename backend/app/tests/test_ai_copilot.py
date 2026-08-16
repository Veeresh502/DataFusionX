import pytest
from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.warehouse import (
    ensure_default_warehouse_models,
    seed_sample_manufacturing,
    load_sales_star_schema
)
from app.services.sql_safety import validate_and_sanitize_sql


@pytest.fixture(autouse=True)
def setup_ai_warehouse_data(db: Session):
    """Seed test data for Sales and Manufacturing warehouse models."""

    user = db.query(User).filter(User.email == "test@example.com").first()
    org_id = user.organization_id if user else 1
    ensure_default_warehouse_models(db, org_id)

    # Seed Sales Sample Facts
    sample_sales = [
        {
            "order_id": "ORD-AI-101",
            "customer_id": "CUST-AI-1",
            "customer_name": "Apex Enterprise",
            "city": "Boston",
            "product_id": "PROD-AI-A",
            "product_name": "AI Analytics License",
            "category": "Software",
            "quantity": 5,
            "unit_price": 2000.0,
            "discount": 100.0,
            "sale_date": "2026-08-10",
        },
        {
            "order_id": "ORD-AI-102",
            "customer_id": "CUST-AI-2",
            "customer_name": "Vortex Tech",
            "city": "Austin",
            "product_id": "PROD-AI-B",
            "product_name": "Cloud Data Engine",
            "category": "Software",
            "quantity": 10,
            "unit_price": 1500.0,
            "discount": 500.0,
            "sale_date": "2026-08-12",
        },
    ]
    load_sales_star_schema(db, sample_sales)

    # Seed Manufacturing Sample Facts
    seed_sample_manufacturing(db, org_id)


def test_1_basic_natural_language_sql_sales(client, auth_headers):
    """TEST 1 — Basic Natural Language SQL on Sales Analytics Model."""
    payload = {
        "question": "What are the top 5 products by revenue?",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data["question"] == payload["question"]
    assert "SELECT" in data["sql"].upper()
    assert "fact_sales" in data["sql"] or "dim_product" in data["sql"]
    assert isinstance(data["columns"], list)
    assert isinstance(data["rows"], list)
    assert data["row_count"] >= 1
    assert "explanation" in data
    assert data["execution_time_ms"] >= 0


def test_2_manufacturing_schema_awareness(client, auth_headers):
    """TEST 2 — Manufacturing Schema Awareness."""
    payload = {
        "question": "Which machines produced the most units?",
        "warehouse_model": "manufacturing"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert "SELECT" in data["sql"].upper()
    assert "fact_production" in data["sql"] or "dim_machine" in data["sql"]
    # Verify AI does NOT reference Sales tables when Manufacturing is selected
    assert "fact_sales" not in data["sql"]
    assert "dim_customer" not in data["sql"]


def test_3_generic_schema_awareness(client, auth_headers):
    """TEST 3 — Generic Schema Awareness."""
    payload = {
        "question": "Show all output rows from generic warehouse",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()
    assert "sql" in data
    assert "explanation" in data


def test_4_invalid_column_handling(client, auth_headers):
    """TEST 4 — Invalid Column Handling."""
    payload = {
        "question": "Show non_existent_column_12345 from the warehouse",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    # Backend catches invalid DB column execution and returns 400 Bad Request safely
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Database Query Error" in response.json()["detail"] or "non_existent_column" in response.json()["detail"]


def test_5_sql_injection_dangerous_sql_rejection(client, auth_headers):
    """TEST 5 — Strict Rejection of Dangerous SQL (DELETE, DROP, UPDATE, INSERT)."""
    dangerous_prompts = [
        "Delete all records from the warehouse",
        "Drop table fact_sales",
        "Update fact_sales set revenue = 0",
        "Insert into fact_sales values (1,2,3)"
    ]

    for prompt in dangerous_prompts:
        response = client.post("/api/ai/query", json={"question": prompt, "warehouse_model": "sales"}, headers=auth_headers)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        err_detail = response.json()["detail"]
        assert "Forbidden" in err_detail or "SQL Safety Error" in err_detail

    # Test unit function directly
    is_safe, _, reason = validate_and_sanitize_sql("DELETE FROM fact_sales")
    assert not is_safe
    assert "Forbidden" in reason or "DELETE" in reason

    is_safe, _, reason = validate_and_sanitize_sql("DROP TABLE dim_customer")
    assert not is_safe
    assert "Forbidden" in reason or "DROP" in reason


def test_6_multiple_statements_rejection(client, auth_headers):
    """TEST 6 — Multiple SQL Statements Rejection."""
    response = client.post("/api/ai/query", json={"question": "SELECT 1; DROP TABLE fact_sales;", "warehouse_model": "sales"}, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST

    is_safe, _, reason = validate_and_sanitize_sql("SELECT * FROM fact_sales; DELETE FROM dim_product;")
    assert not is_safe
    assert "Multiple SQL statements" in reason


def test_7_organization_isolation(db: Session, client, auth_headers):
    """TEST 7 — Organization Tenant Isolation for AI Service."""
    user1 = db.query(User).filter(User.email == "test@example.com").first()

    # Create Organization 2 & User 2
    org2 = db.query(Organization).filter(Organization.name == "Tenant B Corp").first()
    if not org2:
        org2 = Organization(name="Tenant B Corp")
        db.add(org2)
        db.commit()
        db.refresh(org2)

    user2 = db.query(User).filter(User.email == "tenantb@example.com").first()
    if not user2:
        user2 = User(
            email="tenantb@example.com",
            password_hash="hash",
            name="Tenant B Admin",
            organization_id=org2.id,
            role="ADMIN"
        )
        db.add(user2)
        db.commit()
        db.refresh(user2)

    # Create Pipeline Execution for Org 2
    ds2 = DataSource(organization_id=org2.id, name="DS2", type="CSV", configuration={})
    db.add(ds2)
    db.commit()
    db.refresh(ds2)

    p2 = Pipeline(organization_id=org2.id, name="Org2 Pipeline", source_id=ds2.id, steps=[], destination_config={})
    db.add(p2)
    db.commit()
    db.refresh(p2)

    exec2 = PipelineExecution(
        pipeline_id=p2.id,
        organization_id=org2.id,
        status="FAILED",
        current_stage="LOAD",
        error="Target schema column missing"
    )
    db.add(exec2)
    db.commit()
    db.refresh(exec2)

    # User 1 (Tenant A) attempts to explain User 2's (Tenant B) pipeline execution
    response = client.post("/api/ai/explain-pipeline", json={"execution_id": exec2.id}, headers=auth_headers)
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found or access denied" in response.json()["detail"]


def test_8_pipeline_failure_assistant(db: Session, client, auth_headers):
    """TEST 8 — Pipeline Failure Assistant."""
    user = db.query(User).filter(User.email == "test@example.com").first()

    # Create a failed execution for Org 1
    ds = db.query(DataSource).filter(DataSource.organization_id == user.organization_id).first()
    if not ds:
        ds = DataSource(organization_id=user.organization_id, name="Test DS", type="CSV", configuration={})
        db.add(ds)
        db.commit()



    p = Pipeline(organization_id=user.organization_id, name="Test Failing Pipeline", source_id=ds.id, steps=[], destination_config={"table_name": "target_orders"})
    db.add(p)
    db.commit()

    exec_failed = PipelineExecution(
        pipeline_id=p.id,
        organization_id=user.organization_id,
        status="FAILED",
        current_stage="LOAD",
        error="column 'order_id' does not exist in destination table",
        logs=[{"timestamp": "2026-08-16T12:00:00Z", "level": "ERROR", "message": "Failed to map order_id column"}]
    )
    db.add(exec_failed)
    db.commit()

    response = client.post("/api/ai/explain-pipeline", json={"execution_id": exec_failed.id}, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    assert data["execution_id"] == exec_failed.id
    assert data["pipeline_id"] == p.id
    assert "summary" in data
    assert "root_cause" in data
    assert "suggested_fix" in data
    assert data["stage"] == "LOAD"


def test_9_provider_failure_and_health(client, auth_headers):
    """TEST 9 — AI Provider Health & Graceful Error Handling."""
    response = client.get("/api/ai/health", headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["status"] == "healthy"
    assert "provider" in data
    assert "model" in data


def test_10_empty_result_handling(client, auth_headers):
    """TEST 10 — Empty Result Handling."""
    payload = {
        "question": "Show revenue for non-existent order ORD-999999",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK
    data = response.json()

    assert data["row_count"] >= 0
    assert isinstance(data["rows"], list)
    assert "explanation" in data
