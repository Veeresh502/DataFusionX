import pytest
import pandas as pd
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.etl_engine import run_pipeline, transform_dataframe, ETLLogger


@pytest.fixture
def test_org_user(db: Session):
    user = db.query(User).filter(User.email == "test@example.com").first()
    if not user:
        org = Organization(name="Transform Failure Test Org")
        db.add(org)
        db.commit()
        db.refresh(org)
        user = User(email="test@example.com", password_hash="hash", name="Test User", organization_id=org.id, role="ADMIN")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ============================================================
# 1. TEST 1 — INVALID TRANSFORMATION (filter_rows age >= 18)
# ============================================================

def test_1_invalid_transformation_missing_column_fails_pipeline(db: Session, test_org_user):
    """
    TEST 1:
    Filter rows condition 'age >= 18' on dataset without 'age' column.
    EXPECTED:
    - Status = FAILED
    - Read = 10
    - Processed = 0
    - Loaded = 0
    - Error message explicitly mentions column 'age' does not exist.
    - Validation skipped
    - Load skipped
    """
    sample_10_rows = [
        {"id": i, "name": f"Employee {i}", "salary": 50000 + (i * 2000)} for i in range(1, 11)
    ]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Filter Missing Column DS",
        type="CSV",
        configuration={"preview": sample_10_rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Invalid Filter Age Pipeline",
        source_id=ds.id,
        steps=[
            {"category": "transformation", "type": "filter_rows", "condition": "age >= 18"},
            {"category": "validation", "type": "not_null", "rule_type": "NOT_NULL", "column": "name"}
        ],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_invalid_tf"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)

    assert exec_res.status == "FAILED"
    assert exec_res.records_read == 10
    assert exec_res.records_processed == 0
    assert exec_res.records_loaded == 0
    assert "age" in exec_res.error.lower()
    assert "does not exist" in exec_res.error.lower()

    # Check logs
    log_messages = [log["message"] for log in exec_res.logs]
    assert any("Validation skipped because transformation failed" in m for m in log_messages)
    assert any("Load skipped because transformation failed" in m for m in log_messages)


# ============================================================
# 2. TEST 2 — VALID TRANSFORMATION (filter_rows salary >= 60000)
# ============================================================

def test_2_valid_transformation_salary_filter_succeeds(db: Session, test_org_user):
    """
    TEST 2:
    Filter rows condition 'salary >= 60000' on dataset with 'salary' column.
    10 rows created with salaries: 52000, 54000, 56000, 58000, 60000, 62000, 64000, 66000, 68000, 70000.
    Rows matching >= 60000 = 6 rows.
    EXPECTED:
    - Status = SUCCESS
    - Read = 10
    - Loaded = 6
    """
    sample_10_rows = [
        {"id": i, "name": f"Employee {i}", "salary": 50000 + (i * 2000)} for i in range(1, 11)
    ]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Valid Salary Filter DS",
        type="CSV",
        configuration={"preview": sample_10_rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Valid Salary Filter Pipeline",
        source_id=ds.id,
        steps=[
            {"category": "transformation", "type": "filter_rows", "condition": "salary >= 60000"}
        ],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_salary_valid"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)

    assert exec_res.status == "SUCCESS"
    assert exec_res.records_read == 10
    assert exec_res.records_loaded == 6


# ============================================================
# 4. SECTION 15 SPECIFIC REGRESSION TESTS
# ============================================================

def test_remove_duplicates_unselected_entire_row_succeeds(db: Session, test_org_user):
    """REGRESSION TEST: Remove Duplicates with columns left unselected (Entire Row mode) MUST succeed."""
    rows = [
        {"customer_id": 1, "product_id": 10},
        {"customer_id": 1, "product_id": 10}, # Duplicate entire row
        {"customer_id": 2, "product_id": 20}
    ]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Remove Dups Entire Row DS",
        type="CSV",
        configuration={"preview": rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Remove Dups Entire Row Pipeline",
        source_id=ds.id,
        steps=[{"category": "transformation", "type": "remove_duplicates", "columns": []}],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_rem_dups_entire"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "SUCCESS"
    assert exec_res.records_read == 3
    assert exec_res.records_loaded == 2


def test_remove_duplicates_selected_columns_succeeds(db: Session, test_org_user):
    """REGRESSION TEST: Remove Duplicates with selected column subset MUST succeed."""
    rows = [
        {"customer_id": 1, "product_id": 10},
        {"customer_id": 1, "product_id": 99}, # Duplicate customer_id only
        {"customer_id": 2, "product_id": 20}
    ]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Remove Dups Selected Col DS",
        type="CSV",
        configuration={"preview": rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Remove Dups Selected Col Pipeline",
        source_id=ds.id,
        steps=[{"category": "transformation", "type": "remove_duplicates", "columns": ["customer_id"]}],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_rem_dups_subset"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "SUCCESS"
    assert exec_res.records_read == 3
    assert exec_res.records_loaded == 2


def test_fill_null_unselected_columns_succeeds(db: Session, test_org_user):
    """Fill NULL without columns specified fills all NULL columns across dataset."""
    rows = [{"id": 1, "name": None, "score": None}]
    ds = DataSource(organization_id=test_org_user.organization_id, name="Fill Null All DS", type="CSV", configuration={"preview": rows})
    db.add(ds); db.commit(); db.refresh(ds)
    p = Pipeline(organization_id=test_org_user.organization_id, name="Fill Null All Pipeline", source_id=ds.id, steps=[{"category": "transformation", "type": "fill_null", "fill_value": "N/A"}], destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_fill_null_all"})
    db.add(p); db.commit(); db.refresh(p)
    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "SUCCESS"
    assert exec_res.records_loaded == 1


def test_trim_text_unselected_columns_succeeds(db: Session, test_org_user):
    """Trim Text without columns specified trims all string columns across dataset."""
    rows = [{"id": 1, "name": "  Alice  "}]
    ds = DataSource(organization_id=test_org_user.organization_id, name="Trim All DS", type="CSV", configuration={"preview": rows})
    db.add(ds); db.commit(); db.refresh(ds)
    p = Pipeline(organization_id=test_org_user.organization_id, name="Trim All Pipeline", source_id=ds.id, steps=[{"category": "transformation", "type": "trim_text"}], destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_trim_all"})
    db.add(p); db.commit(); db.refresh(p)
    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "SUCCESS"


def test_rename_columns_missing_mapping_fails(db: Session, test_org_user):
    """Rename Columns with missing or empty mapping fails configuration validation."""
    rows = [{"id": 1}]
    ds = DataSource(organization_id=test_org_user.organization_id, name="Rename Empty DS", type="CSV", configuration={"preview": rows})
    db.add(ds); db.commit(); db.refresh(ds)
    p = Pipeline(organization_id=test_org_user.organization_id, name="Rename Empty Pipeline", source_id=ds.id, steps=[{"category": "transformation", "type": "rename_columns", "mapping": {}}], destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_rename_empty"})
    db.add(p); db.commit(); db.refresh(p)
    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "FAILED"
    assert "Rename Columns requires" in exec_res.error


