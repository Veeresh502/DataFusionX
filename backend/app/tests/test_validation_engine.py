import pytest
import pandas as pd
from fastapi import status
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.organization import Organization
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.etl_engine import validate_dataframe, run_pipeline, ETLLogger
from app.services.dag_compiler import validate_and_compile_dag


@pytest.fixture
def test_org_user(db: Session):
    user = db.query(User).filter(User.email == "test@example.com").first()
    if not user:
        org = Organization(name="Validation Test Org")
        db.add(org)
        db.commit()
        db.refresh(org)
        user = User(email="test@example.com", password_hash="hash", name="Test User", organization_id=org.id, role="ADMIN")
        db.add(user)
        db.commit()
        db.refresh(user)
    return user


# ============================================================
# 1. NOT NULL RULE TESTS
# ============================================================

def test_nn_1_not_null_pass():
    df = pd.DataFrame({"region": ["North", "South", "West", "East"]})
    rules = [{"rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 4
    assert len(invalid_df) == 0
    assert len(errors) == 0


def test_nn_2_not_null_fail():
    df = pd.DataFrame({"region": ["North", None, "West", None]})
    rules = [{"rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 2
    assert len(invalid_df) == 2
    assert len(errors) == 2
    assert "violates NOT NULL" in errors[0]


def test_nn_3_not_null_missing_column():
    df = pd.DataFrame({"customer_id": [1, 2, 3]})
    rules = [{"rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(errors) > 0
    assert "missing" in errors[0].lower()


def test_nn_4_not_null_multiple_nulls():
    df = pd.DataFrame({"region": [None, None, "East", None, "West"]})
    rules = [{"rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(invalid_df) == 3
    assert len(errors) == 3


# ============================================================
# 2. UNIQUE RULE TESTS
# ============================================================

def test_u_1_unique_pass():
    df = pd.DataFrame({"customer_id": ["C001", "C002", "C003", "C004"]})
    rules = [{"rule_type": "UNIQUE", "column": "customer_id", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 4
    assert len(invalid_df) == 0
    assert len(errors) == 0


def test_u_2_unique_fail():
    df = pd.DataFrame({"customer_id": ["C001", "C002", "C001", "C003", "C002"]})
    rules = [{"rule_type": "UNIQUE", "column": "customer_id", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(invalid_df) >= 2
    assert len(errors) >= 2
    assert "violates UNIQUE" in errors[0]


def test_u_3_unique_missing_column():
    df = pd.DataFrame({"other_col": [1, 2, 3]})
    rules = [{"rule_type": "UNIQUE", "column": "nonexistent_column", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(errors) > 0
    assert "missing" in errors[0].lower()


# ============================================================
# 3. RANGE RULE TESTS
# ============================================================

def test_r_1_range_pass():
    df = pd.DataFrame({"temperature": [20, 40, 60, 80]})
    rules = [{"rule_type": "RANGE", "column": "temperature", "min_val": 0, "max_val": 100, "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 4
    assert len(invalid_df) == 0


def test_r_2_range_fail():
    df = pd.DataFrame({"temperature": [20, 40, 150, -10]})
    rules = [{"rule_type": "RANGE", "column": "temperature", "min_val": 0, "max_val": 100, "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(invalid_df) == 2
    assert len(errors) == 2


def test_r_3_range_boundary():
    df = pd.DataFrame({"temperature": [0, 100]})
    rules = [{"rule_type": "RANGE", "column": "temperature", "min_val": 0, "max_val": 100, "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 2
    assert len(invalid_df) == 0


# ============================================================
# 4. REGEX RULE TESTS
# ============================================================

def test_regex_1_pass():
    df = pd.DataFrame({"email": ["veeresh@example.com", "rahul@example.com", "sneha@example.com"]})
    rules = [{"rule_type": "REGEX", "column": "email", "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 3
    assert len(invalid_df) == 0


def test_regex_2_fail():
    df = pd.DataFrame({"email": ["veeresh@example.com", "invalid-email", "sneha@example.com"]})
    rules = [{"rule_type": "REGEX", "column": "email", "pattern": r"^[\w\.-]+@[\w\.-]+\.\w+$", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 2
    assert len(invalid_df) == 1
    assert "violates REGEX" in errors[0]


# ============================================================
# 5. MULTI-RULE & TRANSFORM ORDER TESTS
# ============================================================

def test_transform_before_validate_fixes_nulls(db: Session, test_org_user):
    """Verify that fill_null transformation before NOT_NULL validation allows pipeline to PASS."""
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Null Repair Test DS",
        type="CSV",
        configuration={
            "preview": [
                {"item_id": "I-101", "region": "North"},
                {"item_id": "I-102", "region": None},
                {"item_id": "I-103", "region": "South"}
            ]
        }
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Fill Null Then Validate Pipeline",
        source_id=ds.id,
        steps=[
            {"category": "transformation", "type": "fill_null", "columns": ["region"], "fill_value": "Unknown"},
            {"category": "validation", "type": "not_null", "rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}
        ],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_null_fixed"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "SUCCESS"
    assert exec_res.records_failed == 0
    assert exec_res.records_loaded == 3


def test_validation_failure_blocks_load(db: Session, test_org_user):
    """STRICT LOAD PROTECTION: Validation error MUST fail pipeline and block LOAD (records_loaded == 0)."""
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Validation Failure DS",
        type="CSV",
        configuration={
            "preview": [
                {"order_id": "O-1", "region": "North"},
                {"order_id": "O-2", "region": None},
                {"order_id": "O-3", "region": "West"}
            ]
        }
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Failing Validation Pipeline",
        source_id=ds.id,
        steps=[
            {"category": "validation", "type": "not_null", "rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}
        ],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_should_not_exist"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)
    assert exec_res.status == "FAILED"
    assert exec_res.records_loaded == 0
    assert exec_res.records_failed >= 1
    assert "Validation Failure" in exec_res.error


# ============================================================
# 6. CASE INSENSITIVE COLUMN MATCHING
# ============================================================

def test_case_insensitive_column_matching():
    df = pd.DataFrame({"region": ["North", "South", "East"]})
    rules = [{"rule_type": "NOT_NULL", "column": "Region", "severity": "ERROR"}]
    logger = ETLLogger()
    valid_df, invalid_df, errors = validate_dataframe(df, rules, logger)

    assert len(valid_df) == 3
    assert len(invalid_df) == 0
    assert len(errors) == 0


# ============================================================
# 7. REGRESSION TEST FOR CURRENT BUG (Section 29)
# ============================================================

def test_regression_bug_validation_failure_csv(db: Session, test_org_user):
    """
    REGRESSION TEST FOR USER BUG:
    Dataset: 5 records with NULL in region.
    Pipeline: CSV -> Remove Duplicates -> NOT NULL region -> PostgreSQL Target.
    EXPECTED: 5 records read, invalid_records > 0, FAILED, records_loaded == 0.
    """
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Validation Failure CSV Source",
        type="CSV",
        configuration={
            "preview": [
                {"id": 1, "customer": "Acme", "region": "North"},
                {"id": 2, "customer": "Globex", "region": None},
                {"id": 3, "customer": "Soylent", "region": "West"},
                {"id": 4, "customer": "Initech", "region": None},
                {"id": 5, "customer": "Umbrella", "region": "East"}
            ]
        }
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    # Simulate Visual DAG compilation for: CSV -> Remove Duplicates -> NOT NULL -> PostgreSQL Target
    nodes = [
        {"id": "n1", "category": "source", "type": "sourceNode", "data": {"node_type": "csv", "source_id": ds.id}},
        {"id": "n2", "category": "transformation", "type": "transformationNode", "data": {"step_type": "remove_duplicates", "columns": []}},
        {"id": "n3", "category": "validation", "type": "validationNode", "data": {"rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}},
        {"id": "n4", "category": "destination", "type": "destinationNode", "data": {"destination_type": "POSTGRES_TABLE", "table_name": "target_regression_bug"}}
    ]
    edges = [
        {"source": "n1", "target": "n2"},
        {"source": "n2", "target": "n3"},
        {"source": "n3", "target": "n4"}
    ]

    is_valid, errors, compiled_steps, src_id, dest_cfg = validate_and_compile_dag(nodes, edges)
    assert is_valid, f"DAG compilation failed: {errors}"
    assert any(s.get("category") == "validation" for s in compiled_steps), "Validation node category lost in DAG compilation!"

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Regression Bug Pipeline",
        source_id=ds.id,
        steps=compiled_steps,
        destination_config=dest_cfg
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_res = run_pipeline(p.id, db)

    assert exec_res.records_read == 5
    assert exec_res.records_failed == 2
    assert exec_res.status == "FAILED"
    assert exec_res.records_loaded == 0
    assert "Validation Failure" in exec_res.error


# ============================================================
# 8. M11 AI FAILURE ASSISTANT INTEGRATION TEST
# ============================================================

def test_m11_ai_explains_validation_failure(client, auth_headers, db: Session, test_org_user):
    """Verify that M11 AI Assistant correctly diagnoses a validation failure."""
    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Failing Pipeline for AI",
        source_id=1,
        steps=[],
        destination_config={"table_name": "target_ai_test"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_failed = PipelineExecution(
        pipeline_id=p.id,
        organization_id=test_org_user.organization_id,
        status="FAILED",
        current_stage="VALIDATE",
        error="Validation Failure: Row 1: Column 'region' violates NOT NULL constraint",
        logs=[{"timestamp": "2026-08-22T12:00:00Z", "level": "ERROR", "message": "Column 'region' violates NOT NULL constraint"}]
    )
    db.add(exec_failed)
    db.commit()
    db.refresh(exec_failed)

    resp = client.post("/api/ai/explain-pipeline", json={"execution_id": exec_failed.id}, headers=auth_headers)
    assert resp.status_code == status.HTTP_200_OK, resp.text
    data = resp.json()

    assert data["stage"] == "VALIDATE"
    assert "validation" in data["summary"].lower() or "quality" in data["summary"].lower()


# ============================================================
# 9. CELERY WORKER TASK VALIDATION STATUS TESTS
# ============================================================

def test_celery_task_all_invalid_records_fails(db: Session, test_org_user):
    """TEST 1 & 3: Celery task execution with 10 invalid records must set DB status = FAILED and records_loaded = 0."""
    from app.tasks.pipeline_tasks import execute_pipeline_task

    invalid_rows = [{"id": i, "region": None} for i in range(1, 11)]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Celery All Invalid DS",
        type="CSV",
        configuration={"preview": invalid_rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Celery Failing Pipeline",
        source_id=ds.id,
        steps=[{"category": "validation", "type": "not_null", "rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_celery_invalid"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_rec = PipelineExecution(
        pipeline_id=p.id,
        organization_id=test_org_user.organization_id,
        status="PENDING",
        current_stage="QUEUED"
    )
    db.add(exec_rec)
    db.commit()
    db.refresh(exec_rec)

    res = execute_pipeline_task(exec_rec.id, db=db)
    db.refresh(exec_rec)

    assert res["status"] == "FAILED"
    assert exec_rec.status == "FAILED"
    assert exec_rec.current_stage == "FAILED"
    assert exec_rec.records_read == 10
    assert exec_rec.records_failed == 10
    assert exec_rec.records_loaded == 0
    assert "Validation Failure" in exec_rec.error


def test_celery_task_all_valid_records_succeeds(db: Session, test_org_user):
    """TEST 2: Celery task execution with all valid records sets status = SUCCESS and records_loaded > 0."""
    from app.tasks.pipeline_tasks import execute_pipeline_task

    valid_rows = [{"id": i, "region": f"Region-{i}"} for i in range(1, 11)]
    ds = DataSource(
        organization_id=test_org_user.organization_id,
        name="Celery All Valid DS",
        type="CSV",
        configuration={"preview": valid_rows}
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)

    p = Pipeline(
        organization_id=test_org_user.organization_id,
        name="Celery Passing Pipeline",
        source_id=ds.id,
        steps=[{"category": "validation", "type": "not_null", "rule_type": "NOT_NULL", "column": "region", "severity": "ERROR"}],
        destination_config={"destination_type": "POSTGRES_TABLE", "table_name": "target_celery_valid"}
    )
    db.add(p)
    db.commit()
    db.refresh(p)

    exec_rec = PipelineExecution(
        pipeline_id=p.id,
        organization_id=test_org_user.organization_id,
        status="PENDING",
        current_stage="QUEUED"
    )
    db.add(exec_rec)
    db.commit()
    db.refresh(exec_rec)

    res = execute_pipeline_task(exec_rec.id, db=db)
    db.refresh(exec_rec)

    assert res["status"] == "SUCCESS"
    assert exec_rec.status == "SUCCESS"
    assert exec_rec.current_stage == "COMPLETE"
    assert exec_rec.records_read == 10
    assert exec_rec.records_failed == 0
    assert exec_rec.records_loaded == 10

