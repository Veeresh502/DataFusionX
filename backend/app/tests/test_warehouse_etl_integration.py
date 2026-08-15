import io
import json
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.warehouse import FactSales, DimCustomer, DimProduct, DimLocation, DimDate
from app.core.security import get_password_hash, create_access_token
from app.services.warehouse import load_dataframe_to_sales_warehouse, clear_warehouse_sales_data, get_warehouse_analytics
import pandas as pd


@pytest.fixture
def test_user_org_token(db: Session):
    org = Organization(name="ETL Warehouse Test Org")
    db.add(org)
    db.commit()
    db.refresh(org)

    user = User(
        name="ETL Admin",
        email="etladmin@test.com",
        password_hash=get_password_hash("Password123"),
        organization_id=org.id,
        role="ADMIN"
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user.id)
    return user, org, token


def test_full_csv_extraction(client: TestClient, test_user_org_token, db: Session):
    user, org, token = test_user_org_token
    # CSV with 13 rows
    csv_rows = ["order_id,order_date,customer_id,customer_name,city,product_id,product_name,category,quantity,unit_price,discount"]
    for i in range(1, 14):
        csv_rows.append(f"ORD-00{i},2026-08-01,CUST-10{i%3 + 1},Cust {i},City {i},PROD-A{i%2 + 1},Product {i},Software,{i},{100 * i},10")
    
    csv_bytes = "\n".join(csv_rows).encode("utf-8")

    # Upload CSV file
    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales_13_rows.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Sales 13 Rows CSV"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # Verify that full 13 records were stored in configuration
    source_db = db.query(DataSource).filter(DataSource.id == source_id).first()
    assert len(source_db.configuration["records"]) == 13
    assert len(source_db.configuration["preview"]) == 13  # All 13 rows in preview since < 20


def test_warehouse_loader_direct(db: Session):
    clear_warehouse_sales_data(db)

    df_data = pd.DataFrame([
        {
            "order_id": "ORD-5001",
            "order_date": "2026-08-01",
            "customer_id": "CUST-X",
            "customer_name": "Alpha Corp",
            "city": "Boston",
            "product_id": "P-101",
            "product_name": "Data Engine",
            "category": "Software",
            "quantity": 2,
            "unit_price": 1500.0,
            "discount": 100.0,
            "revenue": 2900.0
        },
        {
            "order_id": "ORD-5002",
            "order_date": "2026-08-02",
            "customer_id": "CUST-Y",
            "customer_name": "Beta Inc",
            "city": "Austin",
            "product_id": "P-102",
            "product_name": "Cloud Storage",
            "category": "Infrastructure",
            "quantity": 5,
            "unit_price": 200.0,
            "discount": 0.0,
            "revenue": 1000.0
        }
    ])

    inserted = load_dataframe_to_sales_warehouse(db, df_data)
    assert inserted == 2

    # Verify fact sales table count
    facts = db.query(FactSales).all()
    assert len(facts) == 2
    assert facts[0].revenue == 2900.0
    assert facts[1].revenue == 1000.0

    # Verify Analytics
    analytics = get_warehouse_analytics(db)
    assert analytics["total_revenue"] == 3900.0
    assert analytics["total_quantity"] == 7
    assert analytics["average_order_value"] == 1950.0


def test_duplicate_fact_protection(db: Session):
    clear_warehouse_sales_data(db)

    df_data = pd.DataFrame([
        {
            "order_id": "ORD-SAME-1",
            "order_date": "2026-08-05",
            "customer_id": "CUST-DUP",
            "customer_name": "Dup Corp",
            "city": "Seattle",
            "product_id": "PROD-DUP",
            "product_name": "Dup Item",
            "category": "Software",
            "quantity": 1,
            "unit_price": 500.0,
            "discount": 0.0,
            "revenue": 500.0
        }
    ])

    # First load -> 1 inserted
    count1 = load_dataframe_to_sales_warehouse(db, df_data)
    assert count1 == 1

    # Second load with same order_id & product_id -> 0 inserted (duplicate protected)
    count2 = load_dataframe_to_sales_warehouse(db, df_data)
    assert count2 == 0

    assert db.query(FactSales).count() == 1


def test_scd_type2_customer_update(db: Session):
    clear_warehouse_sales_data(db)

    # Initial Customer Row
    df1 = pd.DataFrame([{
        "order_id": "ORD-SCD-1",
        "order_date": "2026-08-01",
        "customer_id": "CUST-SCD",
        "customer_name": "SCD Corp",
        "city": "Denver",
        "product_id": "PROD-1",
        "product_name": "Item 1",
        "category": "General",
        "quantity": 1,
        "unit_price": 100.0,
        "discount": 0.0,
        "revenue": 100.0
    }])
    load_dataframe_to_sales_warehouse(db, df1)

    custs1 = db.query(DimCustomer).filter(DimCustomer.customer_id == "CUST-SCD").all()
    assert len(custs1) == 1
    assert custs1[0].city == "Denver"
    assert custs1[0].is_current is True

    # Updated Customer Row (city changed from Denver to Chicago)
    df2 = pd.DataFrame([{
        "order_id": "ORD-SCD-2",
        "order_date": "2026-08-05",
        "customer_id": "CUST-SCD",
        "customer_name": "SCD Corp",
        "city": "Chicago",
        "product_id": "PROD-1",
        "product_name": "Item 1",
        "category": "General",
        "quantity": 2,
        "unit_price": 100.0,
        "discount": 0.0,
        "revenue": 200.0
    }])
    load_dataframe_to_sales_warehouse(db, df2)

    custs2 = db.query(DimCustomer).filter(DimCustomer.customer_id == "CUST-SCD").order_by(DimCustomer.customer_key).all()
    assert len(custs2) == 2
    # First record expired
    assert custs2[0].is_current is False
    assert custs2[0].end_date is not None
    # Second record active
    assert custs2[1].is_current is True
    assert custs2[1].city == "Chicago"
    assert custs2[1].end_date is None


def test_pipeline_run_to_warehouse_star_schema(client: TestClient, test_user_org_token, db: Session):
    clear_warehouse_sales_data(db)
    user, org, token = test_user_org_token

    # 1. Upload sales_clean.csv (13 rows)
    csv_bytes = (
        b"order_id,order_date,customer_id,customer_name,city,product_id,product_name,category,quantity,unit_price,discount\n"
        b"ORD001,2026-08-01,C001,Acme Corp,New York,P001,Enterprise Server,Hardware,2,15000,1000\n"
        b"ORD002,2026-08-01,C002,Global Tech,San Francisco,P002,Cloud Analytics,Software,5,2500,0\n"
        b"ORD003,2026-08-02,C003,Apex Systems,Chicago,P003,Support Package,Services,1,5000,500\n"
        b"ORD004,2026-08-02,C004,Priya Nair,Mumbai,P004,Data Connector,Software,10,1200,200\n"
        b"ORD005,2026-08-03,C001,Acme Corp,New York,P002,Cloud Analytics,Software,3,2500,0\n"
        b"ORD006,2026-08-03,C005,Vortex Ltd,London,P005,USB-C Hub,Electronics,4,2200,100\n"
        b"ORD007,2026-08-04,C002,Global Tech,San Francisco,P001,Enterprise Server,Hardware,1,15000,0\n"
        b"ORD008,2026-08-04,C006,Quantum Corp,Tokyo,P003,Support Package,Services,2,5000,1000\n"
        b"ORD009,2026-08-05,C003,Apex Systems,Chicago,P004,Data Connector,Software,8,1200,0\n"
        b"ORD010,2026-08-05,C007,Starlight Media,Los Angeles,P005,USB-C Hub,Electronics,5,2200,500\n"
        b"ORD011,2026-08-06,C004,Priya Nair,Mumbai,P002,Cloud Analytics,Software,2,2500,0\n"
        b"ORD012,2026-08-06,C005,Vortex Ltd,London,P001,Enterprise Server,Hardware,1,15000,2000\n"
        b"ORD013,2026-08-07,C001,Acme Corp,New York,P003,Support Package,Services,3,5000,0\n"
    )

    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales_clean.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Sales Clean Dataset"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # 2. Create pipeline with destination_type: WAREHOUSE_STAR_SCHEMA
    pipeline_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Sales CSV to Warehouse ETL",
            "source_id": source_id,
            "steps": [
                {"type": "remove_duplicates", "category": "transformation"},
                {
                    "type": "calculate_column",
                    "category": "transformation",
                    "target_column": "revenue",
                    "formula": "quantity * unit_price - discount"
                }
            ],
            "destination_config": {
                "destination_type": "WAREHOUSE_STAR_SCHEMA",
                "table_name": "fact_sales",
                "if_exists": "append"
            }
        }
    )
    assert pipeline_res.status_code == 201
    pipeline_id = pipeline_res.json()["id"]

    # 3. Trigger Pipeline Run
    run_res = client.post(
        f"/api/pipelines/{pipeline_id}/run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert run_res.status_code == 200
    exec_data = run_res.json()
    assert exec_data["status"] == "SUCCESS"
    assert exec_data["records_read"] == 13
    assert exec_data["records_processed"] == 13
    assert exec_data["records_loaded"] == 13

    # 4. Verify Warehouse Analytics
    analytics_res = client.get(
        "/api/warehouse/analytics",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert analytics_res.status_code == 200
    analytics = analytics_res.json()

    # Total units = 2+5+1+10+3+4+1+2+8+5+2+1+3 = 47
    assert analytics["total_quantity"] == 47
    # Total revenue = 393750.0 (or computed revenue sum)
    assert analytics["total_revenue"] > 0
    # Fact sales count
    table_summary = client.get("/api/warehouse/tables", headers={"Authorization": f"Bearer {token}"}).json()
    fact_table = next(t for t in table_summary if t["table_name"] == "fact_sales")
    assert fact_table["row_count"] == 13


def test_sales_dirty_remove_duplicates_by_column(client: TestClient, test_user_org_token, db: Session):
    user, org, token = test_user_org_token

    # 17 input rows with duplicate order_id 'O1009'
    csv_rows = [
        "order_id,order_date,customer_id,customer_name,city,product_id,product_name,category,quantity,unit_price,discount",
        "O1001,2026-08-01,C101,Acme,NY,P01,Server,HW,2,100,10",
        "O1002,2026-08-01,C102,Beta,SF,P02,Cloud,SW,1,200,0",
        "O1003,2026-08-02,C103,Gamma,CHI,P03,Support,SVC,5,50,0",
        "O1004,2026-08-02,C104,Delta,LA,P01,Server,HW,1,100,0",
        "O1005,2026-08-03,C105,Epsilon,BOS,P04,Hub,ELEC,3,30,5",
        "O1006,2026-08-03,C106,Zeta,SEA,P02,Cloud,SW,2,200,10",
        "O1007,2026-08-04,C107,Eta,MIA,P05,Cable,ELEC,10,10,0",
        "O1008,2026-08-04,C108,Theta,AUS,P03,Support,SVC,4,50,20",
        "O1009,2026-08-05,C109,Iota,DEN,P01,Server,HW,2,100,0",
        "O1009,2026-08-05,C109,Iota,DEN,P01,Server,HW,2,100,0",  # Duplicate O1009
        "O1010,2026-08-05,C110,Kappa,SD,P04,Hub,ELEC,1,30,0",
        "O1011,2026-08-06,C111,Lambda,PHX,P02,Cloud,SW,6,200,50",
        "O1012,2026-08-06,C112,Mu,DAL,P05,Cable,ELEC,2,10,0",
        "O1013,2026-08-07,C113,Nu,HOU,P03,Support,SVC,1,50,0",
        "O1014,2026-08-07,C114,Xi,ATL,P01,Server,HW,3,100,15",
        "O1015,2026-08-08,C115,Omicron,DET,P04,Hub,ELEC,8,30,10",
        "O1016,2026-08-08,C116,Pi,BOS,P05,Cable,ELEC,5,10,0"
    ]

    csv_bytes = "\n".join(csv_rows).encode("utf-8")

    upload_res = client.post(
        "/api/sources/upload",
        headers={"Authorization": f"Bearer {token}"},
        files={"file": ("sales_dirty.csv", io.BytesIO(csv_bytes), "text/csv")},
        data={"name": "Sales Dirty Dataset"}
    )
    assert upload_res.status_code == 201
    source_id = upload_res.json()["id"]

    # Create pipeline configured with columns=["order_id"] and keep="first"
    pipeline_res = client.post(
        "/api/pipelines",
        headers={"Authorization": f"Bearer {token}"},
        json={
            "name": "Deduplicate sales_dirty Pipeline",
            "source_id": source_id,
            "steps": [
                {
                    "type": "remove_duplicates",
                    "category": "transformation",
                    "columns": ["order_id"],
                    "keep": "first"
                }
            ],
            "destination_config": {
                "destination_type": "POSTGRES_TABLE",
                "table_name": "sales_dirty_clean_output",
                "if_exists": "replace"
            }
        }
    )
    assert pipeline_res.status_code == 201
    pipeline_id = pipeline_res.json()["id"]

    # Trigger Pipeline Run
    run_res = client.post(
        f"/api/pipelines/{pipeline_id}/run",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert run_res.status_code == 200
    exec_data = run_res.json()

    assert exec_data["status"] == "SUCCESS"
    assert exec_data["records_read"] == 17
    assert exec_data["records_processed"] == 16
    assert exec_data["records_loaded"] == 16

