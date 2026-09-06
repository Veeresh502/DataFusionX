import pytest
import pandas as pd
import numpy as np
from sqlalchemy.orm import Session
from app.models.organization import Organization
from app.models.user import User
from app.models.data_source import DataSource
from app.services.ai_service import analyze_data_quality_service
from app.services.profiling import (
    profile_dataframe,
    calculate_deterministic_quality_score,
    detect_anomalies_and_findings,
    extract_dataframe_from_data_source,
    COMPLETENESS_WEIGHT,
    UNIQUENESS_WEIGHT,
    VALIDITY_WEIGHT,
    MAX_TOTAL_PENALTY,
    PENALTY_CRITICAL,
    PENALTY_WARNING
)


def get_or_create_test_user(db: Session):
    org = db.query(Organization).filter(Organization.name == "Generalized Test Org").first()
    if not org:
        org = Organization(name="Generalized Test Org")
        db.add(org); db.commit(); db.refresh(org)

    user = db.query(User).filter(User.email == "generalized_tester@example.com").first()
    if not user:
        user = User(
            email="generalized_tester@example.com",
            password_hash="hash",
            name="Generalized Tester",
            organization_id=org.id,
            role="ADMIN"
        )
        db.add(user); db.commit(); db.refresh(user)
    return user


# 1. Arbitrary Schemas & Unseen Column Names
def test_arbitrary_unseen_columns_and_types():
    df = pd.DataFrame({
        "device_uuid": [f"DEV-{i}" for i in range(20)],
        "voltage_mv": [3200 + i * 10 for i in range(19)] + [15000],  # 15000 is IQR outlier
        "firmware_tag": ["v1.0.1", "V1.0.1", "v1.0.1", "v1.0.2"] * 5,  # Casing inconsistency
        "admin_contact": ["ops@iot.internal"] * 19 + ["invalid-contact-string"],  # Invalid email format
        "is_calibrated": [True] * 20,  # Boolean column
        "null_heavy_sensor": [None] * 15 + [42.0] * 5  # 75% NULL
    })

    res = profile_dataframe(df, source_name="iot_telemetry.json")

    assert res["summary"]["row_count"] == 20
    assert res["summary"]["column_count"] == 6

    # Verify column profiles are generated without hardcoding
    col_names = [c["name"] for c in res["column_profiles"]]
    assert set(col_names) == {"device_uuid", "voltage_mv", "firmware_tag", "admin_contact", "is_calibrated", "null_heavy_sensor"}

    # Outlier detection on arbitrary column
    voltage_prof = next(c for c in res["column_profiles"] if c["name"] == "voltage_mv")
    assert voltage_prof["outlier_count"] == 1
    assert voltage_prof["q1"] is not None
    assert voltage_prof["q3"] is not None
    assert voltage_prof["iqr"] > 0
    assert voltage_prof["lower_bound"] is not None
    assert voltage_prof["upper_bound"] is not None

    # Quality score reconciliation
    qs = res["quality_scores"]
    comp = qs["components"]["completeness"]["value"]
    uniq = qs["components"]["uniqueness"]["value"]
    val = qs["components"]["validity"]["value"]

    expected_base = round((comp * COMPLETENESS_WEIGHT) + (uniq * UNIQUENESS_WEIGHT) + (val * VALIDITY_WEIGHT), 2)
    assert abs(qs["components"]["base_weighted_score"] - expected_base) < 0.05

    expected_final = max(0.0, min(100.0, round(expected_base - qs["components"]["total_penalties"], 1)))
    assert abs(qs["score"] - expected_final) < 0.2


# 2. Edge Case: Empty Dataset (0 rows, 4 columns)
def test_edge_case_empty_dataset():
    df = pd.DataFrame(columns=["alpha", "beta", "gamma", "delta"])
    res = profile_dataframe(df, source_name="empty_test.csv")

    assert res["summary"]["row_count"] == 0
    assert res["summary"]["column_count"] == 4
    assert res["summary"]["duplicate_rows"] == 0
    assert len(res["column_profiles"]) == 0

    # Must contain an empty dataset finding
    empty_findings = [f for f in res["findings"] if f["category"] == "ROW_COUNT_ANOMALY"]
    assert len(empty_findings) == 1
    assert empty_findings[0]["severity"] == "CRITICAL"
    assert empty_findings[0]["penalty"] == PENALTY_CRITICAL


# 3. Edge Case: Single Row Dataset (1 row, 3 columns)
def test_edge_case_single_row_dataset():
    df = pd.DataFrame([{"colA": 100, "colB": "Active", "colC": 99.5}])
    res = profile_dataframe(df, source_name="single_row.csv")

    assert res["summary"]["row_count"] == 1
    assert res["summary"]["column_count"] == 3
    assert res["summary"]["duplicate_rows"] == 0
    assert res["quality_scores"]["completeness"] == 100.0
    assert res["quality_scores"]["uniqueness"] == 100.0
    assert res["quality_scores"]["validity"] == 100.0
    assert res["quality_scores"]["score"] >= 90.0


# 4. Edge Case: 100% Duplicated Dataset
def test_edge_case_fully_duplicated_dataset():
    row = {"product_id": "P1", "category": "Gadget", "price": 19.99}
    df = pd.DataFrame([row] * 10)  # 10 identical rows
    res = profile_dataframe(df, source_name="all_duplicates.csv")

    assert res["summary"]["row_count"] == 10
    assert res["summary"]["duplicate_rows"] == 9
    assert res["quality_scores"]["uniqueness"] == 10.0  # 1 distinct row out of 10 = 10%
    dup_findings = [f for f in res["findings"] if f["category"] == "DUPLICATES"]
    assert len(dup_findings) >= 1
    assert any(f["severity"] == "CRITICAL" for f in dup_findings)


# 5. Edge Case: 100% Null Column
def test_edge_case_all_null_column():
    df = pd.DataFrame({
        "id": [1, 2, 3, 4, 5],
        "entirely_null": [None, None, None, None, None]
    })
    res = profile_dataframe(df, source_name="all_null_col.csv")

    null_prof = next(c for c in res["column_profiles"] if c["name"] == "entirely_null")
    assert null_prof["null_count"] == 5
    assert null_prof["null_percentage"] == 100.0
    assert null_prof["completeness_percentage"] == 0.0

    null_findings = [f for f in res["findings"] if f["category"] == "NULL_SPIKE" and f["column"] == "entirely_null"]
    assert len(null_findings) == 1
    assert null_findings[0]["severity"] == "CRITICAL"
    assert null_findings[0]["penalty"] == PENALTY_CRITICAL


# 6. Mathematical Score Reconciliation & Penalties Caps
def test_mathematical_score_reconciliation_and_penalties():
    summary = {"row_count": 100, "column_count": 5, "duplicate_rows": 5}
    column_profiles = [
        {"null_count": 10, "invalid_format_count": 2, "invalid_date_count": 0},
        {"null_count": 0, "invalid_format_count": 0, "invalid_date_count": 0},
        {"null_count": 0, "invalid_format_count": 0, "invalid_date_count": 0},
        {"null_count": 0, "invalid_format_count": 0, "invalid_date_count": 0},
        {"null_count": 0, "invalid_format_count": 0, "invalid_date_count": 0},
    ]
    findings = [
        {"severity": "CRITICAL", "penalty": 10.0, "category": "NULL_SPIKE"},
        {"severity": "CRITICAL", "penalty": 10.0, "category": "DUPLICATES"},
        {"severity": "WARNING", "penalty": 3.0, "category": "NUMERIC_OUTLIER"},
        {"severity": "WARNING", "penalty": 3.0, "category": "TEXT_INCONSISTENCY"},
    ]

    qs = calculate_deterministic_quality_score(summary, column_profiles, findings)

    # Base metrics check
    assert qs["completeness"] > 0
    assert qs["uniqueness"] == 95.0  # 95 distinct / 100
    assert qs["validity"] > 0

    base_score = qs["components"]["base_weighted_score"]
    total_penalties = qs["components"]["total_penalties"]
    final_score = qs["score"]

    # Deductions mathematically reconcile
    assert total_penalties == 26.0  # 10 + 10 + 3 + 3
    assert final_score == round(max(0.0, min(100.0, base_score - total_penalties)), 1)
    assert qs["components"]["findings_penalties"]["critical_penalty"] == 20.0
    assert qs["components"]["findings_penalties"]["warning_penalty"] == 6.0


# 7. Quality Issues Table 1:1 Mapping with Findings
def test_quality_issues_mapping_and_transparency():
    df = pd.DataFrame({
        "cust_id": ["C1", "C2", "C3", "C4"],
        "email": ["a@b.com", "invalid-email", "c@d.com", "e@f.com"],
        "balance": [100, 150, 120, 95000]  # Outlier
    })
    res = profile_dataframe(df, source_name="customers_banking.csv")

    findings = res["findings"]
    issues = res["quality_issues"]

    assert len(issues) == len(findings)
    for issue in issues:
        assert issue["severity"] in ["CRITICAL", "WARNING", "INFO"]
        assert issue["category"] != ""
        assert issue["column"] in ["cust_id", "email", "balance", "dataset", "schema"]
        assert "penalty" in issue
        assert issue["penalty"] >= 0.0


# 8. CSV vs JSON Equivalence (Normalized pipeline)
def test_csv_and_json_normalization_equivalence():
    data = [
        {"item": "Widget A", "qty": 10, "price": 5.50},
        {"item": "Widget B", "qty": 20, "price": 7.25},
        {"item": "Widget C", "qty": 15, "price": 6.00},
    ]
    df_csv = pd.DataFrame(data)
    df_json = pd.DataFrame(data)

    res_csv = profile_dataframe(df_csv, source_name="items.csv")
    res_json = profile_dataframe(df_json, source_name="items.json")

    assert res_csv["summary"]["row_count"] == res_json["summary"]["row_count"]
    assert res_csv["summary"]["column_count"] == res_json["summary"]["column_count"]
    assert res_csv["quality_scores"]["score"] == res_json["quality_scores"]["score"]
    assert len(res_csv["column_profiles"]) == len(res_json["column_profiles"])
