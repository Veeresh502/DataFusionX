import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.warehouse import DimCustomer, DimProduct, DimDate, DimLocation, FactSales
from app.core.security import get_password_hash, create_access_token
from app.services.warehouse import (
    populate_dim_date,
    upsert_dim_customer_scd2,
    upsert_dim_product,
    upsert_dim_location,
    load_sales_star_schema,
    get_warehouse_analytics,
)


@pytest.fixture
def wh_setup(db: Session):
    org = Organization(name="Warehouse Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="DW Architect",
        email="dwarch@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return user, org, token


def test_dim_date_population(db: Session):
    count = populate_dim_date(db, start_year=2025, end_year=2026)
    assert count > 0
    d_row = db.query(DimDate).filter(DimDate.date_key == 20260808).first()
    assert d_row is not None
    assert d_row.year == 2026
    assert d_row.month_name == "August"


def test_scd_type_2_customer(db: Session):
    cust_id = "CUST-999"

    # Initial Insert
    key1 = upsert_dim_customer_scd2(db, cust_id, "Old Name Inc", "Boston")
    row1 = db.query(DimCustomer).filter(DimCustomer.customer_key == key1).first()
    assert row1.customer_name == "Old Name Inc"
    assert row1.is_current is True
    assert row1.end_date is None

    # Update Customer attributes -> triggers SCD Type 2
    key2 = upsert_dim_customer_scd2(db, cust_id, "New Name Inc", "New York")
    assert key2 != key1  # New surrogate key generated!

    # Old record should be expired
    old_row = db.query(DimCustomer).filter(DimCustomer.customer_key == key1).first()
    assert old_row.is_current is False
    assert old_row.end_date is not None

    # New record should be active
    new_row = db.query(DimCustomer).filter(DimCustomer.customer_key == key2).first()
    assert new_row.customer_name == "New Name Inc"
    assert new_row.city == "New York"
    assert new_row.is_current is True


def test_star_schema_fact_loading_and_analytics(db: Session):
    records = [
        {
            "order_id": "ORD-1",
            "customer_id": "C-1",
            "customer_name": "Cust A",
            "city": "Chicago",
            "product_id": "P-1",
            "product_name": "Prod 1",
            "category": "Gadgets",
            "quantity": 2,
            "unit_price": 50.0,
            "discount": 10.0,
            "sale_date": "2026-08-01",
        },
        {
            "order_id": "ORD-2",
            "customer_id": "C-2",
            "customer_name": "Cust B",
            "city": "Dallas",
            "product_id": "P-2",
            "product_name": "Prod 2",
            "category": "Widgets",
            "quantity": 1,
            "unit_price": 200.0,
            "discount": 0.0,
            "sale_date": "2026-08-02",
        }
    ]

    inserted = load_sales_star_schema(db, records)
    assert inserted == 2

    # Verify Fact records and foreign key linkage
    facts = db.query(FactSales).all()
    assert len(facts) == 2
    assert facts[0].revenue == 90.0  # (2 * 50) - 10

    # Verify analytical metrics calculation
    analytics = get_warehouse_analytics(db)
    assert analytics["total_revenue"] == 290.0  # 90 + 200
    assert analytics["total_quantity"] == 3
    assert analytics["average_order_value"] == 145.0  # 290 / 2
    assert len(analytics["revenue_by_product"]) == 2
    assert len(analytics["revenue_by_category"]) == 2


def test_warehouse_api_endpoints(client: TestClient, wh_setup):
    user, org, token = wh_setup

    # 1. Seed sample sales
    seed_res = client.post(
        "/api/warehouse/seed-sample-sales",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert seed_res.status_code == 201

    # 2. Get Tables Summary
    tables_res = client.get(
        "/api/warehouse/tables",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert tables_res.status_code == 200
    tbl_data = tables_res.json()
    assert len(tbl_data) >= 5

    # 3. Inspect table detail for fact_sales
    detail_res = client.get(
        "/api/warehouse/tables/fact_sales",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert detail_res.status_code == 200
    detail = detail_res.json()
    assert detail["table_name"] == "fact_sales"
    assert len(detail["columns"]) >= 9
    assert len(detail["sample_records"]) > 0

    # 4. Get Analytical Metrics
    analytics_res = client.get(
        "/api/warehouse/analytics",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert analytics_res.status_code == 200
    metrics = analytics_res.json()
    assert metrics["total_revenue"] > 0
    assert metrics["average_order_value"] > 0
