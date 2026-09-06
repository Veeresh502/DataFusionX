import pytest
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.user import User
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.services.ai_service import analyze_data_quality_service
from app.services.profiling import profile_dataframe, calculate_deterministic_quality_score, detect_anomalies_and_findings
import pandas as pd


def get_test_users(db: Session):
    org_a = db.query(Organization).filter(Organization.name == "M13 Quality Org A").first()
    if not org_a:
        org_a = Organization(name="M13 Quality Org A")
        db.add(org_a); db.commit(); db.refresh(org_a)

    user_a = db.query(User).filter(User.email == "user_m13_a@example.com").first()
    if not user_a:
        user_a = User(email="user_m13_a@example.com", password_hash="hash", name="User A", organization_id=org_a.id, role="ADMIN")
        db.add(user_a); db.commit(); db.refresh(user_a)

    org_b = db.query(Organization).filter(Organization.name == "M13 Quality Org B").first()
    if not org_b:
        org_b = Organization(name="M13 Quality Org B")
        db.add(org_b); db.commit(); db.refresh(org_b)

    user_b = db.query(User).filter(User.email == "user_m13_b@example.com").first()
    if not user_b:
        user_b = User(email="user_m13_b@example.com", password_hash="hash", name="User B", organization_id=org_b.id, role="ADMIN")
        db.add(user_b); db.commit(); db.refresh(user_b)

    return user_a, user_b


def create_datasource(db: Session, user: User, name: str, ds_type: str, preview_data: list) -> DataSource:
    ds = DataSource(
        organization_id=user.organization_id,
        name=name,
        type=ds_type,
        configuration={"preview": preview_data}
    )
    db.add(ds); db.commit(); db.refresh(ds)
    return ds


# TEST 1 — Clean Dataset
def test_1_clean_dataset(db: Session):
    user_a, _ = get_test_users(db)
    clean_data = [
        {"employee_id": "EMP01", "name": "Alice", "salary": 85000},
        {"employee_id": "EMP02", "name": "Bob", "salary": 72000},
    ]
    ds = create_datasource(db, user_a, "clean_employees.csv", "CSV", clean_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    assert res["quality_score"]["score"] >= 90.0
    assert res["quality_score"]["status"] == "EXCELLENT"
    assert res["summary_counts"]["critical"] == 0


# TEST 2 — NULL Detection
def test_2_null_detection(db: Session):
    user_a, _ = get_test_users(db)
    null_data = [
        {"employee_id": "EMP01", "salary": 85000},
        {"employee_id": "EMP02", "salary": None},
        {"employee_id": "EMP03", "salary": None},
        {"employee_id": "EMP04", "salary": 90000},
        {"employee_id": "EMP05", "salary": 75000},
    ]
    ds = create_datasource(db, user_a, "null_employees.csv", "CSV", null_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    null_findings = [f for f in res["findings"] if f["category"] == "NULL_SPIKE" and f["column"] == "salary"]
    assert len(null_findings) == 1
    assert null_findings[0]["metric"]["null_count"] == 2
    assert null_findings[0]["metric"]["null_percentage"] == 40.0
    assert "Fill NULL" in null_findings[0]["recommendation"]


# TEST 3 — Duplicate Detection
def test_3_duplicate_detection(db: Session):
    user_a, _ = get_test_users(db)
    dup_data = [
        {"employee_id": "EMP01", "name": "Alice", "dept": "HR"},
        {"employee_id": "EMP01", "name": "Alice", "dept": "HR"},
        {"employee_id": "EMP02", "name": "Bob", "dept": "IT"},
    ]
    ds = create_datasource(db, user_a, "dup_employees.csv", "CSV", dup_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    dup_findings = [f for f in res["findings"] if f["category"] == "DUPLICATES"]
    assert len(dup_findings) >= 1
    assert any("duplicate" in f["finding"].lower() for f in dup_findings)


# TEST 4 — Numeric Outliers (IQR)
def test_4_numeric_outliers_iqr(db: Session):
    user_a, _ = get_test_users(db)
    salaries = [45000, 48000, 50000, 52000, 55000, 58000, 60000, 62000, 65000, 250000]
    outlier_data = [{"employee_id": f"EMP{i}", "salary": s} for i, s in enumerate(salaries, 1)]
    ds = create_datasource(db, user_a, "outlier_employees.csv", "CSV", outlier_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    outlier_findings = [f for f in res["findings"] if f["category"] == "NUMERIC_OUTLIER" and f["column"] == "salary"]
    assert len(outlier_findings) == 1
    assert "Potential statistical outlier" in outlier_findings[0]["finding"]
    assert outlier_findings[0]["metric"]["outlier_count"] >= 1


# TEST 5 — Text Inconsistency (Casing Normalization)
def test_5_text_casing_inconsistency(db: Session):
    user_a, _ = get_test_users(db)
    casing_data = [
        {"employee_id": "EMP01", "department": "Engineering"},
        {"employee_id": "EMP02", "department": "engineering"},
        {"employee_id": "EMP03", "department": "ENGINEERING"},
        {"employee_id": "EMP04", "department": "Sales"},
    ]
    ds = create_datasource(db, user_a, "casing_employees.csv", "CSV", casing_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    casing_findings = [f for f in res["findings"] if f["category"] == "TEXT_INCONSISTENCY" and f["column"] == "department"]
    assert len(casing_findings) == 1
    assert "Normalize Text" in casing_findings[0]["recommendation"]


# TEST 6 — Invalid Format Detection
def test_6_invalid_format_detection(db: Session):
    user_a, _ = get_test_users(db)
    format_data = [
        {"employee_id": "EMP01", "email": "alice@example.com"},
        {"employee_id": "EMP02", "email": "invalid-email-address"},
    ]
    ds = create_datasource(db, user_a, "format_employees.csv", "CSV", format_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    format_findings = [f for f in res["findings"] if f["category"] == "INVALID_FORMAT"]
    assert len(format_findings) == 1
    assert format_findings[0]["metric"]["invalid_format_count"] == 1


# TEST 7 — Schema Mismatch for Domain Warehouse
def test_7_schema_mismatch_sales_analytics(db: Session):
    user_a, _ = get_test_users(db)
    inv_data = [{"item_id": "INV100", "stock": 50}]
    ds = create_datasource(db, user_a, "inventory_data_m13.csv", "CSV", inv_data)

    res = analyze_data_quality_service(db, user_a, ds.id, target_model_slug="sales")

    schema_findings = [f for f in res["findings"] if f["category"] == "SCHEMA_MISMATCH"]
    assert len(schema_findings) == 1
    assert "Sales Analytics" in schema_findings[0]["finding"]


# TEST 8 — Row Count Anomaly Detection
def test_8_row_count_anomaly_detection(db: Session):
    user_a, _ = get_test_users(db)
    data = [{"id": i} for i in range(10)]
    ds = create_datasource(db, user_a, "row_drop_data.csv", "CSV", data)

    # First analysis creates historical profile (1000 rows simulated in profile)
    hist_prof = {"summary": {"row_count": 1000}}
    df = pd.DataFrame(data)
    findings, _ = detect_anomalies_and_findings(df, source_name=ds.name, historical_profile=hist_prof)

    row_findings = [f for f in findings if f["category"] == "ROW_COUNT_ANOMALY"]
    assert len(row_findings) == 1
    assert "CRITICAL" in row_findings[0]["severity"]
    assert row_findings[0]["metric"]["current_rows"] == 10


# TEST 10 — Transformation Loss Analysis
def test_10_transformation_loss_analysis(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_datasource(db, user_a, "tf_loss_data.csv", "CSV", [{"id": 1}])

    hist_execs = [{
        "execution_id": 101,
        "records_read": 10000,
        "records_processed": 10000,
        "records_loaded": 6200,
        "records_failed": 0,
        "status": "COMPLETED"
    }]

    df = pd.DataFrame([{"id": 1}])
    findings, _ = detect_anomalies_and_findings(df, source_name=ds.name, historical_executions=hist_execs)

    tf_findings = [f for f in findings if f["category"] == "TRANSFORMATION_LOSS"]
    assert len(tf_findings) == 1
    assert tf_findings[0]["metric"]["loss_percentage"] == 38.0


# TEST 12 — No Historical Data (No invented baseline)
def test_12_no_historical_data_baseline_handling(db: Session):
    user_a, _ = get_test_users(db)
    ds = create_datasource(db, user_a, "first_time_ds.csv", "CSV", [{"id": 1}])

    res = analyze_data_quality_service(db, user_a, ds.id)

    hist_item = res["historical_comparison"][0]
    assert hist_item["has_history"] is False
    assert "Historical comparison unavailable." in hist_item["change_description"]


# TEST 13 — M12 Integration Suggested Pipeline Prompt
def test_13_m12_integration_suggested_prompt(db: Session):
    user_a, _ = get_test_users(db)
    casing_data = [{"employee_id": "EMP01", "department": "Engineering"}, {"employee_id": "EMP02", "department": "engineering"}]
    ds = create_datasource(db, user_a, "casing_m12.csv", "CSV", casing_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    casing_finding = next(f for f in res["findings"] if f["category"] == "TEXT_INCONSISTENCY")
    assert casing_finding["suggested_pipeline_prompt"] is not None
    assert "Normalize text casing" in casing_finding["suggested_pipeline_prompt"]


# TEST 14 & 15 — Generic & JSON Datasets
def test_14_and_15_generic_and_json_datasets(db: Session):
    user_a, _ = get_test_users(db)
    sensor_data = [{"sensor_id": "S1", "temp": 22.5, "humidity": 55}]
    ds = create_datasource(db, user_a, "sensorreadings.json", "JSON", sensor_data)

    res = analyze_data_quality_service(db, user_a, ds.id)

    assert res["source_type"] == "JSON"
    assert "sensor_id" in [c["name"] for c in res["column_profiles"]]


# TEST 16 — Tenant Isolation Protection
def test_16_tenant_isolation_protection(db: Session):
    user_a, user_b = get_test_users(db)
    ds_a = create_datasource(db, user_a, "org_a_secret_m13.csv", "CSV", [{"secret": 999}])

    with pytest.raises(ValueError) as exc_info:
        analyze_data_quality_service(db, user_b, ds_a.id)

    assert "access denied" in str(exc_info.value).lower() or "not found" in str(exc_info.value).lower()


# TEST 17 — AI Provider Failure Graceful Fallback
def test_17_ai_provider_failure_fallback(db: Session, monkeypatch):
    user_a, _ = get_test_users(db)
    ds = create_datasource(db, user_a, "ai_fail_data.csv", "CSV", [{"employee_id": "EMP01", "salary": 80000}])

    def mock_fail(*args, **kwargs):
        raise Exception("LLM Provider connection timeout")

    from app.services.ai_provider import MockLLMProvider
    monkeypatch.setattr(MockLLMProvider, "analyze_data_quality_intelligence", mock_fail)

    res = analyze_data_quality_service(db, user_a, ds.id)

    # Profiling & Quality Score must STILL work 100%!
    assert res["ai_explanation_available"] is False
    assert "AI explanation unavailable." in res["ai_summary"]
    assert res["quality_score"]["score"] >= 90.0
