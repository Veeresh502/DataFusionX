import pytest
import pandas as pd
from sqlalchemy.orm import Session

from app.models.organization import Organization
from app.models.user import User
from app.models.warehouse_model import WarehouseModel
from app.models.warehouse_table import WarehouseTable
from app.models.warehouse import (
    FactSales, DimCustomer, DimProduct, DimLocation, DimDate,
    FactProduction, DimMachine, DimPlant
)
from app.services.warehouse import (
    ensure_default_warehouse_models,
    load_dataframe_to_warehouse,
    get_warehouse_models_list,
    get_warehouse_model_by_identifier,
    get_generic_model_analytics,
    get_warehouse_analytics,
    get_manufacturing_analytics,
    clear_warehouse_sales_data,
    clear_warehouse_manufacturing_data,
)


@pytest.fixture
def clean_warehouse_db(db: Session):
    """Ensures clean warehouse database state before testing."""
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)
    yield db
    clear_warehouse_sales_data(db)
    clear_warehouse_manufacturing_data(db)


def get_or_create_test_org(db: Session) -> Organization:
    org = db.query(Organization).first()
    if not org:
        org = Organization(name="Test Organization")
        db.add(org)
        db.commit()
        db.refresh(org)
    return org


def test_warehouse_model_auto_registration(clean_warehouse_db: Session):
    org = get_or_create_test_org(clean_warehouse_db)

    models = get_warehouse_models_list(clean_warehouse_db, org.id)
    assert len(models) >= 2
    
    slugs = [m.slug for m in models]
    assert "sales" in slugs
    assert "manufacturing" in slugs

    sales_wm = get_warehouse_model_by_identifier(clean_warehouse_db, "sales", org.id)
    assert sales_wm.domain == "SALES"
    assert len(sales_wm.tables) == 5

    mfg_wm = get_warehouse_model_by_identifier(clean_warehouse_db, "manufacturing", org.id)
    assert mfg_wm.domain == "MANUFACTURING"
    assert len(mfg_wm.tables) == 4


def test_1_existing_sales_etl(clean_warehouse_db: Session):
    """TEST 1 — Existing Sales Star Schema loading and analytics."""
    sales_data = [
        {
            "order_id": "O1001",
            "order_date": "2026-08-01",
            "customer_id": "C101",
            "customer_name": "Rohan Sharma",
            "city": "Mumbai",
            "product_id": "P500",
            "product_name": "Pro Wireless Headphones",
            "category": "Electronics",
            "quantity": 2,
            "unit_price": 5000.0,
            "discount": 500.0,
            "revenue": 9500.0,
        },
        {
            "order_id": "O1002",
            "order_date": "2026-08-02",
            "customer_id": "C102",
            "customer_name": "Ananya Roy",
            "city": "Delhi",
            "product_id": "P501",
            "product_name": "Ultra Smartwatch",
            "category": "Electronics",
            "quantity": 1,
            "unit_price": 12000.0,
            "discount": 1000.0,
            "revenue": 11000.0,
        },
    ]

    df = pd.DataFrame(sales_data)
    loaded = load_dataframe_to_warehouse(clean_warehouse_db, df, warehouse_model_identifier="sales")
    assert loaded == 2

    assert clean_warehouse_db.query(FactSales).count() == 2
    assert clean_warehouse_db.query(DimCustomer).count() == 2
    assert clean_warehouse_db.query(DimProduct).count() == 2
    assert clean_warehouse_db.query(DimLocation).count() == 2
    assert clean_warehouse_db.query(DimDate).count() >= 2

    analytics = get_warehouse_analytics(clean_warehouse_db)
    assert analytics["total_revenue"] == 20500.0
    assert analytics["total_quantity"] == 3


def test_2_manufacturing_etl(clean_warehouse_db: Session):
    """TEST 2 — Manufacturing Star Schema loading and analytics."""
    org = get_or_create_test_org(clean_warehouse_db)

    mfg_data = [
        {
            "production_id": "PR-501",
            "production_date": "2026-08-10",
            "machine_id": "M-100",
            "machine_name": "CNC Lathe Alpha",
            "plant_id": "PL-01",
            "plant_name": "Austin Gigafactory",
            "units_produced": 1200,
            "defect_count": 24,
            "operating_hours": 8.0,
        },
        {
            "production_id": "PR-502",
            "production_date": "2026-08-10",
            "machine_id": "M-200",
            "machine_name": "Robotic Welder Beta",
            "plant_id": "PL-01",
            "plant_name": "Austin Gigafactory",
            "units_produced": 950,
            "defect_count": 10,
            "operating_hours": 7.5,
        },
    ]

    df = pd.DataFrame(mfg_data)
    loaded = load_dataframe_to_warehouse(clean_warehouse_db, df, warehouse_model_identifier="manufacturing")
    assert loaded == 2

    assert clean_warehouse_db.query(FactProduction).count() == 2
    assert clean_warehouse_db.query(DimMachine).count() == 2
    assert clean_warehouse_db.query(DimPlant).count() == 1
    assert clean_warehouse_db.query(FactSales).count() == 0  # Sales tables untouched

    mfg_analytics = get_manufacturing_analytics(clean_warehouse_db, org.id)
    assert mfg_analytics["total_production_batches"] == 2
    assert mfg_analytics["total_units_produced"] == 2150
    assert mfg_analytics["total_defect_count"] == 34


def test_3_generic_warehouse_explorer(clean_warehouse_db: Session):
    """TEST 3 — Generic Warehouse Explorer lists all registered warehouse models and table metrics."""
    org = get_or_create_test_org(clean_warehouse_db)
    models = get_warehouse_models_list(clean_warehouse_db, org.id)
    assert len(models) >= 2

    sales_wm = next(m for m in models if m.slug == "sales")
    sales_gen = get_generic_model_analytics(clean_warehouse_db, sales_wm)
    assert sales_gen["domain"] == "SALES"
    assert sales_gen["fact_table_count"] == 1
    assert sales_gen["dimension_table_count"] == 4

    mfg_wm = next(m for m in models if m.slug == "manufacturing")
    mfg_gen = get_generic_model_analytics(clean_warehouse_db, mfg_wm)
    assert mfg_gen["domain"] == "MANUFACTURING"
    assert mfg_gen["fact_table_count"] == 1
    assert mfg_gen["dimension_table_count"] == 3


def test_4_dual_pipeline_destination(clean_warehouse_db: Session):
    """TEST 4 — Generic Pipeline Destination routes to Sales vs Manufacturing via same ETL engine."""
    sales_df = pd.DataFrame([
        {
            "order_id": "ORD-GEN-1",
            "order_date": "2026-08-11",
            "customer_id": "C-GEN-1",
            "customer_name": "General Motors",
            "city": "Detroit",
            "product_id": "P-GEN-1",
            "product_name": "Automotive Sensor",
            "category": "Hardware",
            "quantity": 10,
            "unit_price": 250.0,
            "discount": 0.0,
            "revenue": 2500.0,
        }
    ])

    mfg_df = pd.DataFrame([
        {
            "production_id": "MFG-GEN-1",
            "production_date": "2026-08-11",
            "machine_id": "M-GEN-1",
            "machine_name": "Assembly Line 1",
            "plant_id": "PL-GEN-1",
            "plant_name": "Detroit Plant",
            "units_produced": 500,
            "defect_count": 5,
            "operating_hours": 6.0,
        }
    ])

    # Pipeline A -> Sales Warehouse
    loaded_sales = load_dataframe_to_warehouse(
        clean_warehouse_db,
        sales_df,
        dest_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "sales"}
    )
    assert loaded_sales == 1

    # Pipeline B -> Manufacturing Warehouse
    loaded_mfg = load_dataframe_to_warehouse(
        clean_warehouse_db,
        mfg_df,
        dest_config={"destination_type": "WAREHOUSE", "warehouse_model_slug": "manufacturing"}
    )
    assert loaded_mfg == 1

    assert clean_warehouse_db.query(FactSales).count() == 1
    assert clean_warehouse_db.query(FactProduction).count() == 1


def test_5_sales_isolation(clean_warehouse_db: Session):
    """TEST 5 — Loading Manufacturing data does NOT mutate fact_sales."""
    initial_sales_facts = clean_warehouse_db.query(FactSales).count()

    mfg_df = pd.DataFrame([
        {
            "production_id": "PR-ISOLATION-1",
            "production_date": "2026-08-12",
            "machine_id": "M-ISO",
            "machine_name": "Press 1",
            "plant_id": "PL-ISO",
            "plant_name": "Plant 1",
            "units_produced": 800,
            "defect_count": 8,
            "operating_hours": 8.0,
        }
    ])

    load_dataframe_to_warehouse(clean_warehouse_db, mfg_df, warehouse_model_identifier="manufacturing")
    
    assert clean_warehouse_db.query(FactProduction).count() == 1
    assert clean_warehouse_db.query(FactSales).count() == initial_sales_facts


def test_6_manufacturing_isolation(clean_warehouse_db: Session):
    """TEST 6 — Loading Sales data does NOT mutate fact_production."""
    initial_mfg_facts = clean_warehouse_db.query(FactProduction).count()

    sales_df = pd.DataFrame([
        {
            "order_id": "ORD-ISO-1",
            "order_date": "2026-08-12",
            "customer_id": "C-ISO",
            "customer_name": "Iso Customer",
            "city": "Boston",
            "product_id": "P-ISO",
            "product_name": "Iso Widget",
            "category": "Widget",
            "quantity": 5,
            "unit_price": 100.0,
            "discount": 0.0,
            "revenue": 500.0,
        }
    ])

    load_dataframe_to_warehouse(clean_warehouse_db, sales_df, warehouse_model_identifier="sales")

    assert clean_warehouse_db.query(FactSales).count() == 1
    assert clean_warehouse_db.query(FactProduction).count() == initial_mfg_facts


def test_7_organization_isolation(clean_warehouse_db: Session):
    """TEST 7 — Organization A cannot access Organization B's warehouse models."""
    org_a = get_or_create_test_org(clean_warehouse_db)

    # Create Organization B
    org_b = Organization(name="Org B Test")
    clean_warehouse_db.add(org_b)
    clean_warehouse_db.commit()
    clean_warehouse_db.refresh(org_b)

    models_a = get_warehouse_models_list(clean_warehouse_db, org_a.id)
    models_b = get_warehouse_models_list(clean_warehouse_db, org_b.id)

    assert len(models_a) >= 2
    assert len(models_b) >= 2

    # Verify model IDs are distinct and scope-isolated
    model_ids_a = {m.id for m in models_a}
    model_ids_b = {m.id for m in models_b}

    assert model_ids_a.isdisjoint(model_ids_b)

    for m_b in models_b:
        with pytest.raises(ValueError):
            get_warehouse_model_by_identifier(clean_warehouse_db, m_b.id, organization_id=org_a.id)
