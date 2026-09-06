import pytest
import pandas as pd
from sqlalchemy.orm import Session
from sqlalchemy import text, inspect

from app.models.organization import Organization
from app.models.user import User
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.warehouse import FactSales, FactProduction
from app.services.etl_engine import run_pipeline
from app.services.warehouse import (
    ensure_default_warehouse_models,
    get_warehouse_models_list,
    get_warehouse_tables_summary,
    clear_warehouse_sales_data,
    clear_warehouse_manufacturing_data,
)
from app.services.ai_service import process_natural_language_query


@pytest.fixture
def clean_db(db: Session):
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)
    yield db
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)


def get_test_user(db: Session) -> User:
    user = db.query(User).filter(User.email == "test_generic_wh@example.com").first()
    if not user:
        org = Organization(name="Generic Warehouse Test Org")
        db.add(org); db.commit(); db.refresh(org)
        user = User(email="test_generic_wh@example.com", password_hash="hash", name="Generic User", organization_id=org.id, role="ADMIN")
        db.add(user); db.commit(); db.refresh(user)
    return user


# TEST 1 — Generic Warehouse CSV Loading
def test_1_generic_warehouse_csv_inventory_loading(clean_db: Session):
    user = get_test_user(clean_db)
    rows = [
        {"item_id": "INV-001", "item_name": "Widget Alpha", "stock": 15, "warehouse_loc": "NY"},
        {"item_id": "INV-002", "item_name": "Gadget Beta", "stock": 45, "warehouse_loc": "SF"},
    ]
    ds = DataSource(organization_id=user.organization_id, name="Inventory CSV", type="CSV", configuration={"preview": rows})
    clean_db.add(ds); clean_db.commit(); clean_db.refresh(ds)

    p = Pipeline(
        organization_id=user.organization_id,
        name="Inventory Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "inventory"}
    )
    clean_db.add(p); clean_db.commit(); clean_db.refresh(p)

    exec_res = run_pipeline(p.id, clean_db)
    print("\nEXECUTION ERROR:", exec_res.error)
    assert exec_res.status == "SUCCESS"

    assert exec_res.records_loaded == 2

    tables = get_warehouse_tables_summary(clean_db, model_slug_or_id="generic")
    table_names = [t["table_name"] for t in tables]
    assert "inventory" in table_names


# TEST 2 — JSON Generic Warehouse Sensor Readings
def test_2_json_generic_warehouse_sensor_readings(clean_db: Session):
    user = get_test_user(clean_db)
    rows = [
        {"sensor_id": "S101", "temp": 24.5, "humidity": 60.0},
        {"sensor_id": "S102", "temp": 28.1, "humidity": 55.0},
    ]
    ds = DataSource(organization_id=user.organization_id, name="Sensor JSON", type="JSON", configuration={"preview": rows})
    clean_db.add(ds); clean_db.commit(); clean_db.refresh(ds)

    p = Pipeline(
        organization_id=user.organization_id,
        name="Sensor Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "sensor_readings"}
    )
    clean_db.add(p); clean_db.commit(); clean_db.refresh(p)

    exec_res = run_pipeline(p.id, clean_db)
    assert exec_res.status == "SUCCESS"
    assert exec_res.records_loaded == 2


# TEST 3 — Sales Analytics Loading
def test_3_sales_analytics_loading(clean_db: Session):
    user = get_test_user(clean_db)
    rows = [
        {
            "order_id": "ORD-500", "order_date": "2026-08-15", "customer_id": "CUST-9", "customer_name": "Acme",
            "city": "Boston", "product_id": "PROD-9", "product_name": "Data Engine", "category": "Tech",
            "quantity": 1, "unit_price": 5000.0, "discount": 0.0, "revenue": 5000.0
        }
    ]
    ds = DataSource(organization_id=user.organization_id, name="Sales CSV", type="CSV", configuration={"preview": rows})
    clean_db.add(ds); clean_db.commit(); clean_db.refresh(ds)

    p = Pipeline(
        organization_id=user.organization_id,
        name="Sales Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "sales"}
    )
    clean_db.add(p); clean_db.commit(); clean_db.refresh(p)

    exec_res = run_pipeline(p.id, clean_db)
    assert exec_res.status == "SUCCESS"
    assert clean_db.query(FactSales).count() > 0


# TEST 4 — Manufacturing Analytics Loading
def test_4_manufacturing_analytics_loading(clean_db: Session):
    user = get_test_user(clean_db)
    rows = [
        {
            "production_id": "MFG-900", "production_date": "2026-08-15", "machine_id": "M-99", "machine_name": "Stamper",
            "plant_id": "PL-1", "plant_name": "Plant 1", "units_produced": 500, "defect_count": 5, "operating_hours": 4.0
        }
    ]
    ds = DataSource(organization_id=user.organization_id, name="Mfg CSV", type="CSV", configuration={"preview": rows})
    clean_db.add(ds); clean_db.commit(); clean_db.refresh(ds)

    p = Pipeline(
        organization_id=user.organization_id,
        name="Mfg Pipeline",
        source_id=ds.id,
        steps=[],
        destination_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "manufacturing"}
    )
    clean_db.add(p); clean_db.commit(); clean_db.refresh(p)

    exec_res = run_pipeline(p.id, clean_db)
    assert exec_res.status == "SUCCESS"
    assert clean_db.query(FactProduction).count() > 0


# TEST 5 — Domain Isolation
def test_5_generic_warehouse_does_not_affect_star_schemas(clean_db: Session):
    sales_cnt_before = clean_db.query(FactSales).count()
    mfg_cnt_before = clean_db.query(FactProduction).count()

    test_1_generic_warehouse_csv_inventory_loading(clean_db)

    assert clean_db.query(FactSales).count() == sales_cnt_before
    assert clean_db.query(FactProduction).count() == mfg_cnt_before


# TEST 6 — AI Query Generic Warehouse Context
def test_6_ai_query_generic_warehouse_context(clean_db: Session):
    user = get_test_user(clean_db)
    test_1_generic_warehouse_csv_inventory_loading(clean_db)

    res = process_natural_language_query(
        db=clean_db,
        user=user,
        question="Show inventory items where stock is below 20",
        warehouse_model_slug="generic"
    )

    sql = res.get("sql", "").lower()
    assert "inventory" in sql
    assert "fact_sales" not in sql
    assert "fact_production" not in sql


# TEST 7 — AI Query Manufacturing Context
def test_7_ai_query_manufacturing_context(clean_db: Session):
    user = get_test_user(clean_db)
    test_4_manufacturing_analytics_loading(clean_db)

    res = process_natural_language_query(
        db=clean_db,
        user=user,
        question="Show the total units produced by machine",
        warehouse_model_slug="manufacturing"
    )

    sql = res.get("sql", "").lower()
    assert "fact_production" in sql or "dim_machine" in sql


# TEST 8 — AI Query Sales Context
def test_8_ai_query_sales_context(clean_db: Session):
    user = get_test_user(clean_db)
    test_3_sales_analytics_loading(clean_db)

    res = process_natural_language_query(
        db=clean_db,
        user=user,
        question="Show the top products by revenue",
        warehouse_model_slug="sales"
    )

    sql = res.get("sql", "").lower()
    assert "fact_sales" in sql or "dim_product" in sql


# TEST 9 — Model Selector
def test_9_warehouse_model_selector_contains_generic_sales_mfg(clean_db: Session):
    user = get_test_user(clean_db)
    models = get_warehouse_models_list(clean_db, user.organization_id)
    slugs = [m.slug for m in models]

    assert "generic" in slugs
    assert "sales" in slugs
    assert "manufacturing" in slugs
    assert slugs[0] == "generic"
