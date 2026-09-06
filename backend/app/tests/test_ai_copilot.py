import re
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


def test_1_revenue_greater_than_50000(client, auth_headers):
    """TEST 1 — Show all products with revenue greater than 50000."""
    payload = {
        "question": "Show all products with revenue greater than 50000",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    # Query MUST contain HAVING SUM(f.revenue) > 50000
    upper_sql = data["sql"].upper()
    assert "HAVING" in upper_sql, f"SQL missing HAVING clause: {data['sql']}"
    assert "50000" in data["sql"]
    assert not re.search(r'\bLIMIT 5\b', upper_sql), f"Arbitrary LIMIT 5 injected into query: {data['sql']}"
    assert data["row_count"] == 0 or all(float(r.get("total_revenue", 0)) > 50000 for r in data["rows"])
    if data["row_count"] == 0:
        assert "No records matched" in data["explanation"]


def test_2_top_5_products(client, auth_headers):
    """TEST 2 — Show the top 5 products by revenue."""
    payload = {
        "question": "Show the top 5 products by revenue",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "ORDER BY" in upper_sql
    assert re.search(r'\bLIMIT 5\b', upper_sql)


def test_3_revenue_between(client, auth_headers):
    """TEST 3 — Show products with revenue between 10000 and 50000."""
    payload = {
        "question": "Show products with revenue between 10000 and 50000",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "BETWEEN 10000" in upper_sql or "BETWEEN 10000.0" in upper_sql


def test_4_more_than_3_orders(client, auth_headers):
    """TEST 4 — Show customers with more than 3 orders."""
    payload = {
        "question": "Show customers with more than 3 orders",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "HAVING COUNT" in upper_sql or "HAVING" in upper_sql


def test_5_show_all_products_no_arbitrary_limit_5(client, auth_headers):
    """TEST 5 — Show all products (Must not contain arbitrary LIMIT 5)."""
    payload = {
        "question": "Show all products",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert not re.search(r'\bLIMIT 5\b', upper_sql)



def test_6_unit_price_where_vs_having(client, auth_headers):
    """TEST 6 — Show products where unit price is greater than 500."""
    payload = {
        "question": "Show products where unit price is greater than 500",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "WHERE" in upper_sql
    assert "HAVING SUM(UNIT_PRICE)" not in upper_sql


def test_7_avg_revenue_having(client, auth_headers):
    """TEST 7 — Show average revenue by product where average revenue is greater than 10000."""
    payload = {
        "question": "Show average revenue by product where average revenue is greater than 10000",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "HAVING AVG" in upper_sql or "AVG(" in upper_sql


def test_8_nonexistent_column_rejection(client, auth_headers):
    """TEST 8 — Nonexistent field (profit_margin) handling."""
    payload = {
        "question": "Show products by profit_margin",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "not available in the current warehouse schema" in response.json()["detail"] or "profit_margin" in response.json()["detail"]


def test_9_read_only_sql_rejection(client, auth_headers):
    """TEST 9 — Reject mutating SQL (Delete all sales)."""
    payload = {
        "question": "Delete all sales",
        "warehouse_model": "sales"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "Forbidden" in response.json()["detail"] or "SQL Safety Error" in response.json()["detail"]


def test_10_manufacturing_model_awareness(client, auth_headers):
    """TEST 10 — Manufacturing Model Awareness."""
    payload = {
        "question": "Show total production by machine",
        "warehouse_model": "manufacturing"
    }
    response = client.post("/api/ai/query", json=payload, headers=auth_headers)
    assert response.status_code == status.HTTP_200_OK, response.text
    data = response.json()

    upper_sql = data["sql"].upper()
    assert "FACT_PRODUCTION" in upper_sql or "DIM_MACHINE" in upper_sql
    assert "FACT_SALES" not in upper_sql

