import json
import io
import math
import re
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.models.data_profile import DataProfile


# ==============================================================================
# QUALITY ENGINE CONSTANTS & SCORING POLICY
# ==============================================================================
COMPLETENESS_WEIGHT: float = 0.35
UNIQUENESS_WEIGHT: float = 0.35
VALIDITY_WEIGHT: float = 0.30

PENALTY_CRITICAL: float = 10.0
PENALTY_WARNING: float = 3.0
PENALTY_INFO: float = 0.0

MAX_CRITICAL_PENALTY: float = 40.0
MAX_WARNING_PENALTY: float = 15.0
MAX_TOTAL_PENALTY: float = 50.0


def _clean_val(val: Any) -> Any:
    """Sanitize numpy/pandas scalar values for JSON serialization and frontend display."""
    if val is None or pd.isna(val):
        return None
    if isinstance(val, (np.integer, int)):
        return int(val)
    if isinstance(val, (np.floating, float)):
        if math.isnan(val) or math.isinf(val):
            return None
        return round(float(val), 4)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return str(val)
    return str(val)


def assign_penalty(severity: str) -> float:
    """Returns deterministic deduction penalty based on finding severity."""
    sev = str(severity).upper()
    if sev == "CRITICAL":
        return PENALTY_CRITICAL
    elif sev == "WARNING":
        return PENALTY_WARNING
    return PENALTY_INFO


def calculate_deterministic_quality_score(
    summary: Dict[str, Any],
    column_profiles: List[Dict[str, Any]],
    findings: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Calculates deterministic, mathematically reconcilable 0-100 quality score.
    Formula:
      Base Weighted Score = (Completeness × 0.35) + (Uniqueness × 0.35) + (Validity × 0.30)
      Penalties = min(MAX_TOTAL_PENALTY, Sum of Finding Penalties)
      Quality Score = max(0.0, min(100.0, Base Weighted Score - Penalties))
    """
    total_rows = int(summary.get("row_count", 0))
    total_cols = int(summary.get("column_count", 0))
    duplicate_rows = int(summary.get("duplicate_rows", 0))
    distinct_rows = max(0, total_rows - duplicate_rows)

    total_cells = total_rows * total_cols
    total_nulls = sum(int(c.get("null_count", 0)) for c in column_profiles)
    non_null_cells = max(0, total_cells - total_nulls)

    # 1. Base Metrics
    if total_cells > 0:
        completeness = round((non_null_cells / total_cells) * 100.0, 2)
    else:
        completeness = 0.0

    if total_rows > 0:
        uniqueness = round((distinct_rows / total_rows) * 100.0, 2)
    else:
        uniqueness = 0.0

    invalid_cells = sum(
        int(c.get("invalid_format_count", 0)) + int(c.get("invalid_date_count", 0))
        for c in column_profiles
    )

    if non_null_cells > 0 and invalid_cells > 0:
        valid_cells = max(0, non_null_cells - invalid_cells)
        validity = round((valid_cells / non_null_cells) * 100.0, 2)
    else:
        validity = 100.0

    # 2. Component Contributions
    completeness_contrib = round(completeness * COMPLETENESS_WEIGHT, 2)
    uniqueness_contrib = round(uniqueness * UNIQUENESS_WEIGHT, 2)
    validity_contrib = round(validity * VALIDITY_WEIGHT, 2)
    base_weighted_score = round(completeness_contrib + uniqueness_contrib + validity_contrib, 2)

    # 3. Penalties Calculation
    crit_findings = [f for f in findings if f.get("severity") == "CRITICAL"]
    warn_findings = [f for f in findings if f.get("severity") == "WARNING"]

    crit_count = len(crit_findings)
    warn_count = len(warn_findings)

    crit_penalty_raw = sum(float(f.get("penalty", PENALTY_CRITICAL)) for f in crit_findings)
    warn_penalty_raw = sum(float(f.get("penalty", PENALTY_WARNING)) for f in warn_findings)

    crit_penalty = round(min(MAX_CRITICAL_PENALTY, crit_penalty_raw), 2)
    warn_penalty = round(min(MAX_WARNING_PENALTY, warn_penalty_raw), 2)
    total_penalties = round(min(MAX_TOTAL_PENALTY, crit_penalty + warn_penalty), 2)

    schema_penalties = round(sum(float(f.get("penalty", 10.0)) for f in crit_findings if f.get("category") == "SCHEMA_MISMATCH"), 2)
    anomaly_penalties = round(sum(float(f.get("penalty", 10.0)) for f in crit_findings if f.get("category") in ["NULL_SPIKE", "DUPLICATES", "ROW_COUNT_ANOMALY", "TRANSFORMATION_LOSS"]), 2)

    # 4. Final Quality Score
    raw_score = base_weighted_score - total_penalties
    score = round(max(0.0, min(100.0, raw_score)), 1)

    if score >= 90.0:
        status = "EXCELLENT"
        overall_severity = "INFO"
    elif score >= 70.0:
        status = "GOOD"
        overall_severity = "WARNING"
    else:
        status = "POOR"
        overall_severity = "CRITICAL"

    components = {
        "completeness": {
            "value": completeness,
            "weight": COMPLETENESS_WEIGHT,
            "contribution": completeness_contrib
        },
        "uniqueness": {
            "value": uniqueness,
            "weight": UNIQUENESS_WEIGHT,
            "contribution": uniqueness_contrib
        },
        "validity": {
            "value": validity,
            "weight": VALIDITY_WEIGHT,
            "contribution": validity_contrib
        },
        "base_weighted_score": base_weighted_score,
        "anomaly_penalty": anomaly_penalties,
        "schema_penalty": schema_penalties,
        "total_penalties": total_penalties,
        "findings_penalties": {
            "critical_findings_count": crit_count,
            "critical_penalty": crit_penalty,
            "warning_findings_count": warn_count,
            "warning_penalty": warn_penalty
        },
        "formula_description": "Quality Score = max(0, min(100, (Completeness × 0.35 + Uniqueness × 0.35 + Validity × 0.30) - Total Penalties))"
    }

    return {
        "completeness": completeness,
        "uniqueness": uniqueness,
        "validity": validity,
        "overall": score,
        "score": score,
        "quality_score": score,
        "max_score": 100.0,
        "status": status,
        "overall_severity": overall_severity,
        "components": components,
        "breakdown": {
            "base_weighted_score": base_weighted_score,
            "critical_finding_penalty": crit_penalty,
            "warning_finding_penalty": warn_penalty,
            "total_penalties": total_penalties,
            "anomaly_penalty": anomaly_penalties,
            "schema_penalty": schema_penalties
        }
    }


def detect_anomalies_and_findings(
    df: pd.DataFrame,
    source_name: str = "dataset",
    target_model_slug: str = "generic",
    historical_profile: Optional[Dict[str, Any]] = None,
    historical_executions: Optional[List[Dict[str, Any]]] = None
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Performs deterministic, data-driven anomaly detection across dataset columns & metadata.
    Returns: (findings_list, historical_comparison_list)
    """
    findings: List[Dict[str, Any]] = []
    historical_comparison: List[Dict[str, Any]] = []

    total_rows = int(len(df))
    columns = list(df.columns)

    if total_rows == 0:
        findings.append({
            "id": "finding-empty-dataset",
            "column": "dataset",
            "category": "ROW_COUNT_ANOMALY",
            "severity": "CRITICAL",
            "penalty": PENALTY_CRITICAL,
            "finding": "Dataset is empty (0 records).",
            "evidence": ["Row count: 0"],
            "metric": {"row_count": 0},
            "explanation": f"Dataset '{source_name}' contains no records.",
            "recommendation": "Review source extraction pipeline before loading.",
            "suggested_pipeline_prompt": None
        })
        return findings, [{
            "metric_name": "Historical Baseline",
            "current_value": 0,
            "previous_value": None,
            "change_description": "Historical comparison unavailable.",
            "has_history": False
        }]

    # 1. NULL ANALYSIS
    for col in columns:
        series = df[col]
        # Detect missing: pd.isna, None, and for strings empty string or null tokens
        if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
            null_mask = series.isna() | series.astype(str).str.strip().isin(["", "nan", "null", "none", "<na>", "n/a"])
        else:
            null_mask = series.isna()

        null_count = int(null_mask.sum())
        if null_count > 0:
            null_pct = round((null_count / total_rows) * 100, 2)
            severity = "CRITICAL" if null_pct >= 20.0 else "WARNING"
            penalty = assign_penalty(severity)
            model_label = "Generic Warehouse" if target_model_slug == "generic" else target_model_slug.title() + " Analytics"

            findings.append({
                "id": f"finding-null-{col}",
                "column": str(col),
                "category": "NULL_SPIKE",
                "severity": severity,
                "penalty": penalty,
                "finding": f"WARNING: {col} contains NULL values in {null_pct}% of records." if severity == "WARNING" else f"CRITICAL: {col} has high NULL frequency ({null_pct}% NULL values).",
                "evidence": [f"Null count: {null_count} / {total_rows} records ({null_pct}%)"],
                "metric": {"null_count": null_count, "null_percentage": null_pct},
                "explanation": f"Column '{col}' contains {null_count} missing (NULL) values out of {total_rows} records ({null_pct}%).",
                "recommendation": "Consider Fill NULL or review source data before loading.",
                "suggested_pipeline_prompt": f"Fill missing NULL values in column '{col}' with default value and load into {model_label}."
            })

    # 2. DUPLICATE ROW ANALYSIS
    duplicate_rows = int(df.duplicated().sum())
    if duplicate_rows > 0:
        dup_pct = round((duplicate_rows / total_rows) * 100, 2)
        severity = "CRITICAL" if dup_pct >= 10.0 else "WARNING"
        penalty = assign_penalty(severity)
        model_label = "Generic Warehouse" if target_model_slug == "generic" else target_model_slug.title() + " Analytics"

        findings.append({
            "id": "finding-duplicate-rows",
            "column": "dataset",
            "category": "DUPLICATES",
            "severity": severity,
            "penalty": penalty,
            "finding": f"{duplicate_rows} duplicate records were detected ({dup_pct}% of dataset).",
            "evidence": [f"Duplicate rows: {duplicate_rows} / {total_rows}"],
            "metric": {"duplicate_rows": duplicate_rows, "duplicate_percentage": dup_pct},
            "explanation": f"The dataset contains {duplicate_rows} exact duplicate rows across all fields.",
            "recommendation": "Consider Remove Duplicates before loading into data warehouse.",
            "suggested_pipeline_prompt": f"Remove duplicate records from {source_name} and load into {model_label}."
        })

    # Identifier Uniqueness Check (Key / ID columns)
    for col in columns:
        col_lower = str(col).lower()
        col_tokens = set(re.split(r'[^a-zA-Z0-9]+', col_lower))
        is_id_named = bool(col_tokens & {"id", "uuid", "guid", "key", "code", "pk", "hash", "token", "ref", "identifier"}) or col_lower.endswith(("_id", "_key", "_code", "_pk", "_uuid", "_hash", "_ref"))
        
        series = df[col].dropna()
        non_null_count = int(len(series))
        unique_count = int(series.nunique())
        dup_keys = non_null_count - unique_count

        # Check identifier either by naming convention or high-cardinality candidate key
        is_id_candidate = is_id_named or (non_null_count >= 5 and unique_count / non_null_count >= 0.85 and dup_keys > 0 and (pd.api.types.is_string_dtype(series) or pd.api.types.is_integer_dtype(series)))

        if is_id_candidate and dup_keys > 0:
            model_label = "Generic Warehouse" if target_model_slug == "generic" else target_model_slug.title() + " Analytics"
            findings.append({
                "id": f"finding-dup-id-{col}",
                "column": str(col),
                "category": "DUPLICATES",
                "severity": "CRITICAL",
                "penalty": PENALTY_CRITICAL,
                "finding": f"Column '{col}' appears to be an identifier and contains {dup_keys} duplicate values.",
                "evidence": [f"Total records: {non_null_count}", f"Unique values: {unique_count}", f"Duplicate key records: {dup_keys}"],
                "metric": {"unique_count": unique_count, "duplicate_keys": dup_keys},
                "explanation": f"Column '{col}' appears to be a unique key identifier, but contains {dup_keys} non-unique key records.",
                "recommendation": "Review duplicate key records or apply Remove Duplicates based on key column.",
                "suggested_pipeline_prompt": f"Remove duplicate records based on unique key '{col}' and load into {model_label}."
            })

    # 3. NUMERIC ANOMALY DETECTION (Deterministic IQR Outliers)
    for col in columns:
        series = df[col]
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            non_null = series.dropna()
            if len(non_null) >= 4:
                q1 = float(non_null.quantile(0.25))
                q3 = float(non_null.quantile(0.75))
                iqr = q3 - q1
                if iqr > 0:
                    lower_bound = q1 - (1.5 * iqr)
                    upper_bound = q3 + (1.5 * iqr)
                    outliers = non_null[(non_null < lower_bound) | (non_null > upper_bound)]
                    outlier_count = int(len(outliers))
                    if outlier_count > 0:
                        outlier_samples = [_clean_val(v) for v in outliers.head(5).tolist()]
                        findings.append({
                            "id": f"finding-outlier-{col}",
                            "column": str(col),
                            "category": "NUMERIC_OUTLIER",
                            "severity": "WARNING",
                            "penalty": PENALTY_WARNING,
                            "finding": f"Potential statistical outlier: {outlier_count} records in '{col}' are statistical outliers.",
                            "evidence": [
                                f"Q1={_clean_val(q1)}, Q3={_clean_val(q3)}, IQR={_clean_val(iqr)}",
                                f"Lower bound: {_clean_val(lower_bound)}, Upper bound: {_clean_val(upper_bound)}",
                                f"Sample outliers: {outlier_samples}"
                            ],
                            "metric": {
                                "outlier_count": outlier_count,
                                "q1": q1,
                                "q3": q3,
                                "iqr": iqr,
                                "lower_bound": lower_bound,
                                "upper_bound": upper_bound
                            },
                            "explanation": f"Column '{col}' contains {outlier_count} records falling outside the IQR bounds [{_clean_val(lower_bound)}, {_clean_val(upper_bound)}].",
                            "recommendation": f"Review potential statistical outliers in column '{col}' for data entry errors.",
                            "suggested_pipeline_prompt": f"Filter rows where {col} is within expected range and load into Generic Warehouse."
                        })

    # 4. CATEGORICAL ANOMALIES (Casing Inconsistencies)
    for col in columns:
        series = df[col]
        if pd.api.types.is_string_dtype(series) or pd.api.types.is_object_dtype(series):
            non_null = series.dropna().astype(str)
            if not non_null.empty:
                grouped: Dict[str, set] = {}
                for val in non_null:
                    raw = str(val).strip()
                    if not raw:
                        continue
                    lower = raw.lower()
                    if lower not in grouped:
                        grouped[lower] = set()
                    grouped[lower].add(raw)

                variants_found = [raw_set for raw_set in grouped.values() if len(raw_set) > 1]
                if variants_found:
                    variant_samples = [list(vs) for vs in variants_found[:3]]
                    model_label = "Generic Warehouse" if target_model_slug == "generic" else target_model_slug.title() + " Analytics"
                    findings.append({
                        "id": f"finding-casing-{col}",
                        "column": str(col),
                        "category": "TEXT_INCONSISTENCY",
                        "severity": "WARNING",
                        "penalty": PENALTY_WARNING,
                        "finding": f"Inconsistent text representations detected in column '{col}'.",
                        "evidence": [f"Inconsistent text variants: {variant_samples}"],
                        "metric": {"inconsistent_variant_groups": len(variants_found)},
                        "explanation": f"Column '{col}' contains inconsistent text casing/representations (e.g. {variant_samples[0]}).",
                        "recommendation": "Consider Normalize Text before loading.",
                        "suggested_pipeline_prompt": f"Normalize text casing for column '{col}' and load cleaned data into {model_label}."
                    })

    # 5. FORMAT ANOMALIES (Email & Date validation)
    for col in columns:
        col_lower = str(col).lower()
        series = df[col].dropna().astype(str)
        if not series.empty:
            # Email regex check
            if "email" in col_lower or any("@" in v for v in series.head(10)):
                email_regex = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
                invalid_emails = [v for v in series if not email_regex.match(v.strip())]
                if invalid_emails:
                    invalid_cnt = len(invalid_emails)
                    findings.append({
                        "id": f"finding-email-{col}",
                        "column": str(col),
                        "category": "INVALID_FORMAT",
                        "severity": "WARNING",
                        "penalty": PENALTY_WARNING,
                        "finding": f"Format anomaly: {invalid_cnt} records in '{col}' have invalid email formats.",
                        "evidence": [f"Invalid email samples: {invalid_emails[:3]}"],
                        "metric": {"invalid_format_count": invalid_cnt},
                        "explanation": f"Column '{col}' contains {invalid_cnt} email values that do not conform to valid email structure.",
                        "recommendation": "Apply REGEX validation or clean invalid email addresses.",
                        "suggested_pipeline_prompt": f"Validate column '{col}' using email REGEX pattern and load into Generic Warehouse."
                    })

    # 6. SCHEMA ANOMALIES & DOMAIN COMPATIBILITY
    if target_model_slug == "sales":
        sales_keywords = ["order", "revenue", "sale", "quantity", "unit_price", "price", "amount", "customer", "product", "discount"]
        matching_sales = [c for c in columns if any(kw in str(c).lower() for kw in sales_keywords)]
        if len(matching_sales) < 2:
            findings.append({
                "id": "finding-schema-sales-mismatch",
                "column": "schema",
                "category": "SCHEMA_MISMATCH",
                "severity": "CRITICAL",
                "penalty": PENALTY_CRITICAL,
                "finding": f"Schema mismatch: Dataset '{source_name}' is not compatible with Sales Analytics warehouse model.",
                "evidence": [f"Detected columns: {columns}", "Missing required sales fields: order_id, product_id, revenue"],
                "metric": {"matching_sales_columns": len(matching_sales)},
                "explanation": f"Dataset '{source_name}' lacks required sales metrics (e.g., order_id, product_name, revenue). Recommended model: Generic Warehouse.",
                "recommendation": "Use Generic Warehouse destination model instead of Sales Analytics.",
                "suggested_pipeline_prompt": f"Load dataset {source_name} into Generic Warehouse."
            })
    elif target_model_slug == "manufacturing":
        mfg_keywords = ["production", "machine", "plant", "units", "produced", "defect", "hours", "operator"]
        matching_mfg = [c for c in columns if any(kw in str(c).lower() for kw in mfg_keywords)]
        if len(matching_mfg) < 2:
            findings.append({
                "id": "finding-schema-mfg-mismatch",
                "column": "schema",
                "category": "SCHEMA_MISMATCH",
                "severity": "CRITICAL",
                "penalty": PENALTY_CRITICAL,
                "finding": f"Schema mismatch: Dataset '{source_name}' is not compatible with Manufacturing Analytics warehouse model.",
                "evidence": [f"Detected columns: {columns}", "Missing required manufacturing fields: production_id, machine_name, units_produced"],
                "metric": {"matching_mfg_columns": len(matching_mfg)},
                "explanation": f"Dataset '{source_name}' lacks required manufacturing fields (e.g., production_id, machine_name, units_produced). Recommended model: Generic Warehouse.",
                "recommendation": "Use Generic Warehouse destination model instead of Manufacturing Analytics.",
                "suggested_pipeline_prompt": f"Load dataset {source_name} into Generic Warehouse."
            })

    # 7. HISTORICAL BASELINE COMPARISON
    if historical_profile and isinstance(historical_profile, dict):
        hist_sum = historical_profile.get("summary", {})
        hist_rows = hist_sum.get("row_count")
        if hist_rows is not None and hist_rows > 0:
            row_diff_pct = round(((total_rows - hist_rows) / hist_rows) * 100, 1)

            historical_comparison.append({
                "metric_name": "Row Count",
                "current_value": total_rows,
                "previous_value": hist_rows,
                "change_description": f"Row count changed by {row_diff_pct}% compared with baseline ({hist_rows} rows).",
                "has_history": True
            })

            if total_rows < (hist_rows * 0.5):
                findings.append({
                    "id": "finding-row-count-drop",
                    "column": "dataset",
                    "category": "ROW_COUNT_ANOMALY",
                    "severity": "CRITICAL",
                    "penalty": PENALTY_CRITICAL,
                    "finding": f"CRITICAL: Current input contains {total_rows} records compared with recent historical baseline of approx. {hist_rows} records.",
                    "evidence": [f"Current row count: {total_rows}", f"Historical row count: {hist_rows}", f"Reduction: {abs(row_diff_pct)}%"],
                    "metric": {"current_rows": total_rows, "historical_rows": hist_rows, "drop_percentage": abs(row_diff_pct)},
                    "explanation": f"Current input contains {total_rows} records compared with a recent average of approx. {hist_rows} records. This may indicate incomplete source extraction or upstream failure.",
                    "recommendation": "Verify upstream data extraction and verify partial ingestion is not occurring.",
                    "suggested_pipeline_prompt": None
                })
    else:
        historical_comparison.append({
            "metric_name": "Historical Baseline",
            "current_value": total_rows,
            "previous_value": None,
            "change_description": "Historical comparison unavailable.",
            "has_history": False
        })

    # 8. HISTORICAL EXECUTION METRICS (Transformation Loss & Validation Failures)
    if historical_executions and isinstance(historical_executions, list) and len(historical_executions) > 0:
        latest_exec = historical_executions[0]
        read = latest_exec.get("records_read", 0)
        loaded = latest_exec.get("records_loaded", 0)
        failed = latest_exec.get("records_failed", 0)

        if read > 0 and loaded < read:
            loss_cnt = read - loaded
            loss_pct = round((loss_cnt / read) * 100, 1)
            if loss_pct >= 10.0:
                findings.append({
                    "id": "finding-transform-loss",
                    "column": "pipeline_execution",
                    "category": "TRANSFORMATION_LOSS",
                    "severity": "WARNING",
                    "penalty": PENALTY_WARNING,
                    "finding": f"WARNING: {loss_pct}% of records were removed during pipeline transformation/validation.",
                    "evidence": [f"Records read: {read}", f"Records loaded: {loaded}", f"Records lost/filtered: {loss_cnt} ({loss_pct}%)"],
                    "metric": {"records_read": read, "records_loaded": loaded, "loss_percentage": loss_pct},
                    "explanation": f"{loss_cnt} out of {read} records ({loss_pct}%) were filtered out during transformation or validation execution.",
                    "recommendation": "Review pipeline transformation filter rules and validation constraints.",
                    "suggested_pipeline_prompt": None
                })

        if failed > 0:
            severity = "CRITICAL" if failed > (read * 0.2) else "WARNING"
            penalty = assign_penalty(severity)
            findings.append({
                "id": "finding-validation-failures",
                "column": "pipeline_execution",
                "category": "VALIDATION_FAILURES",
                "severity": severity,
                "penalty": penalty,
                "finding": f"{failed} records failed validation rules during the recent execution.",
                "evidence": [f"Records failed validation: {failed} / {read}"],
                "metric": {"records_failed": failed},
                "explanation": f"Pipeline execution failed validation rules on {failed} records.",
                "recommendation": "Inspect validation error logs or adjust validation rules in Visual DAG Builder.",
                "suggested_pipeline_prompt": None
            })

    return findings, historical_comparison


def extract_dataframe_from_data_source(data_source: DataSource) -> pd.DataFrame:
    """
    Extracts complete, normalized pandas DataFrame from DataSource configuration.
    Normalized and reusable for CSV, JSON, Excel, REST, and PostgreSQL datasets.
    """
    if not data_source or not data_source.configuration:
        return pd.DataFrame()

    config = data_source.configuration or {}

    # 1. Complete records list
    records = config.get("records") or config.get("data") or config.get("items")
    if records and isinstance(records, list) and len(records) > 0:
        df = pd.DataFrame(records)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # 2. Preview records
    preview = config.get("preview") or config.get("preview_data") or config.get("rows")
    if preview and isinstance(preview, list) and len(preview) > 0:
        df = pd.DataFrame(preview)
        df.columns = [str(c).strip() for c in df.columns]
        return df

    # 3. Raw file content (CSV or JSON string)
    raw_content = config.get("raw_content") or config.get("file_content")
    if raw_content and isinstance(raw_content, str):
        try:
            if data_source.type and data_source.type.upper() == "JSON":
                parsed = json.loads(raw_content)
                if isinstance(parsed, list):
                    df = pd.DataFrame(parsed)
                elif isinstance(parsed, dict):
                    df = pd.DataFrame([parsed])
                else:
                    df = pd.DataFrame()
            else:
                df = pd.read_csv(io.StringIO(raw_content))
            df.columns = [str(c).strip() for c in df.columns]
            return df
        except Exception:
            pass

    return pd.DataFrame()


def profile_dataframe(
    df: pd.DataFrame,
    source_name: str = "dataset",
    target_model_slug: str = "generic",
    historical_profile: Optional[Dict[str, Any]] = None,
    historical_executions: Optional[List[Dict[str, Any]]] = None
) -> Dict[str, Any]:
    """Generates structured profiling metrics, anomaly findings, and deterministic quality score."""
    total_rows = int(len(df))
    columns = list(df.columns)
    total_cols = int(len(columns))

    # Handle empty dataset gracefully
    if total_rows == 0:
        summary = {
            "row_count": 0,
            "column_count": total_cols,
            "duplicate_rows": 0,
            "memory_bytes": 0,
        }
        findings, hist_comp = detect_anomalies_and_findings(df, source_name, target_model_slug, historical_profile, historical_executions)
        qs = calculate_deterministic_quality_score(summary, [], findings)
        return {
            "summary": summary,
            "column_profiles": [],
            "quality_scores": qs,
            "findings": findings,
            "quality_issues": [
                {
                    "severity": f["severity"],
                    "category": f["category"].replace("_", " ").title(),
                    "column": f["column"],
                    "count": 0,
                    "percentage": 0.0,
                    "penalty": f.get("penalty", 0.0),
                    "description": f["finding"],
                    "evidence": f["evidence"]
                }
                for f in findings
            ],
            "historical_comparison": hist_comp
        }

    duplicate_rows = int(df.duplicated().sum())
    memory_bytes = int(df.memory_usage(deep=True).sum())

    column_profiles = []

    for col in columns:
        try:
            series = df[col]
            # Missing value mask
            if series.dtype == "object" or str(series.dtype) == "string":
                null_mask = series.isna() | series.astype(str).str.strip().isin(["", "nan", "null", "none", "<na>", "n/a"])
            else:
                null_mask = series.isna()

            null_count = int(null_mask.sum())
            non_null_count = int(total_rows - null_count)
            null_pct = round((null_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            completeness_pct = round((non_null_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0

            unique_count = int(series.nunique(dropna=True))
            unique_pct = round((unique_count / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
            dup_val_count = max(0, non_null_count - unique_count)

            raw_dtype = str(series.dtype)
            col_prof: Dict[str, Any] = {
                "name": str(col),
                "data_type": raw_dtype,
                "null_count": null_count,
                "non_null_count": non_null_count,
                "null_percentage": null_pct,
                "completeness_percentage": completeness_pct,
                "unique_count": unique_count,
                "unique_percentage": unique_pct,
                "duplicate_value_count": dup_val_count,
            }

            # Base detected type
            if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
                detected_type = "numeric"
            elif pd.api.types.is_bool_dtype(series):
                detected_type = "boolean"
            elif pd.api.types.is_datetime64_any_dtype(series):
                detected_type = "date"
            else:
                detected_type = "string"

            # 1. Check if numeric column
            if detected_type == "numeric":
                non_null = series.dropna()
                if not non_null.empty:
                    q1 = float(non_null.quantile(0.25))
                    q3 = float(non_null.quantile(0.75))
                    iqr = q3 - q1
                    lower_bound = q1 - (1.5 * iqr)
                    upper_bound = q3 + (1.5 * iqr)

                    outliers_series = non_null[(non_null < lower_bound) | (non_null > upper_bound)] if iqr > 0 else pd.Series([], dtype=float)
                    outlier_count = int(len(outliers_series))
                    outlier_pct = round((outlier_count / len(non_null)) * 100.0, 2) if len(non_null) > 0 else 0.0
                    outlier_vals = [_clean_val(v) for v in outliers_series.head(10).tolist()]
                    affected_indices = [int(idx) for idx in outliers_series.index.tolist()[:10]]

                    col_prof["q1"] = _clean_val(q1)
                    col_prof["q3"] = _clean_val(q3)
                    col_prof["iqr"] = _clean_val(iqr)
                    col_prof["lower_bound"] = _clean_val(lower_bound)
                    col_prof["upper_bound"] = _clean_val(upper_bound)
                    col_prof["min"] = _clean_val(non_null.min())
                    col_prof["max"] = _clean_val(non_null.max())
                    col_prof["mean"] = _clean_val(non_null.mean())
                    col_prof["median"] = _clean_val(non_null.median())
                    col_prof["std"] = _clean_val(non_null.std()) if len(non_null) > 1 else 0.0
                    col_prof["outlier_count"] = outlier_count
                    col_prof["outlier_percentage"] = outlier_pct
                    col_prof["outliers"] = outlier_vals
                    col_prof["affected_row_indices"] = affected_indices

            # 2. Check for Email / Format Detection (if string)
            EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$')
            if detected_type == "string" and non_null_count > 0:
                non_null_str = series.dropna().astype(str).str.strip()
                email_matches = sum(1 for val in non_null_str if EMAIL_REGEX.match(val))
                if (email_matches / non_null_count) >= 0.3:
                    detected_type = "email"
                    col_prof["detected_format"] = "email"
                    col_prof["valid_format_count"] = email_matches
                    col_prof["invalid_format_count"] = int(non_null_count - email_matches)
                    col_prof["format_validity_percentage"] = round((email_matches / non_null_count) * 100.0, 2)

            # 3. Check for Date / Datetime Column
            if detected_type in ["string", "date"] and non_null_count > 0:
                is_date_col = False
                date_series = None
                valid_dates = 0
                invalid_dates = 0
                dt_format = "ISO-8601"

                if pd.api.types.is_datetime64_any_dtype(series):
                    is_date_col = True
                    date_series = series.dropna()
                    valid_dates = int(len(date_series))
                    invalid_dates = 0
                    dt_format = "ISO-8601"
                else:
                    try:
                        non_null_s = series.dropna().astype(str).str.strip()
                        # Do not treat pure integer sequences like IDs as dates
                        if not non_null_s.str.isdigit().all():
                            parsed = pd.to_datetime(non_null_s, errors="coerce", format="mixed")
                            valid_dates = int(parsed.notnull().sum())
                            if valid_dates > 0 and (valid_dates / non_null_count) >= 0.7:
                                is_date_col = True
                                date_series = parsed.dropna()
                                invalid_dates = int(non_null_count - valid_dates)
                                sample_val = str(non_null_s.iloc[0])
                                if "-" in sample_val:
                                    dt_format = "YYYY-MM-DD"
                                elif "/" in sample_val:
                                    dt_format = "MM/DD/YYYY"
                                else:
                                    dt_format = "Mixed / ISO-8601"
                            elif valid_dates > 0 and (valid_dates / non_null_count) >= 0.2:
                                col_prof["potential_type"] = "date"
                    except Exception:
                        pass

                if is_date_col and date_series is not None and not date_series.empty:
                    detected_type = "date"
                    col_prof["valid_date_count"] = valid_dates
                    col_prof["invalid_date_count"] = invalid_dates
                    col_prof["min_date"] = str(date_series.min())
                    col_prof["max_date"] = str(date_series.max())
                    col_prof["detected_date_format"] = dt_format
                    try:
                        dist_df = date_series.dt.to_period("M").value_counts().sort_index().reset_index()
                        dist_df.columns = ["period", "count"]
                        col_prof["date_distribution"] = [
                            {"period": str(row["period"]), "count": int(row["count"])}
                            for _, row in dist_df.head(12).iterrows()
                        ]
                    except Exception:
                        col_prof["date_distribution"] = []

            col_prof["detected_type"] = detected_type

            # Categorical Stats
            if detected_type != "numeric" or unique_count <= 10:
                col_prof["cardinality"] = unique_count
                top_counts = series.value_counts(dropna=True).head(5)
                col_prof["top_values"] = [
                    {
                        "value": _clean_val(val),
                        "count": int(cnt),
                        "percentage": round((cnt / total_rows) * 100.0, 2) if total_rows > 0 else 0.0
                    }
                    for val, cnt in top_counts.items()
                ]

            column_profiles.append(col_prof)
        except Exception as err:
            column_profiles.append({
                "name": str(col),
                "data_type": "unknown",
                "null_count": 0,
                "non_null_count": 0,
                "null_percentage": 0.0,
                "completeness_percentage": 0.0,
                "unique_count": 0,
                "unique_percentage": 0.0,
                "duplicate_value_count": 0,
                "status": "error",
                "reason": str(err)
            })

    summary = {
        "row_count": total_rows,
        "column_count": total_cols,
        "duplicate_rows": duplicate_rows,
        "memory_bytes": memory_bytes,
    }

    # Detect Anomaly Findings & Historical Baseline
    findings, historical_comparison = detect_anomalies_and_findings(
        df, source_name, target_model_slug, historical_profile, historical_executions
    )

    # Calculate Deterministic Quality Score (0 - 100)
    qs = calculate_deterministic_quality_score(summary, column_profiles, findings)

    # Structured Quality Issues list (1:1 with findings for complete reconciliation)
    quality_issues = []
    for f in findings:
        col_name = f.get("column", "dataset")
        cat = f.get("category", "ANOMALY")
        sev = f.get("severity", "WARNING")
        penalty = f.get("penalty", assign_penalty(sev))

        count = f.get("metric", {}).get("outlier_count") or f.get("metric", {}).get("null_count") or f.get("metric", {}).get("duplicate_rows") or f.get("metric", {}).get("invalid_format_count") or 1
        pct = f.get("metric", {}).get("outlier_percentage") or f.get("metric", {}).get("null_percentage") or f.get("metric", {}).get("duplicate_percentage") or 0.0

        quality_issues.append({
            "severity": sev,
            "category": cat.replace("_", " ").title(),
            "column": col_name,
            "count": count,
            "percentage": pct,
            "penalty": penalty,
            "description": f.get("finding", ""),
            "evidence": f.get("evidence", [])
        })

    return {
        "summary": summary,
        "column_profiles": column_profiles,
        "quality_scores": qs,
        "findings": findings,
        "quality_issues": quality_issues,
        "historical_comparison": historical_comparison
    }


def get_or_create_data_profile(
    data_source: DataSource,
    db: Session,
    target_model_slug: str = "generic"
) -> DataProfile:
    """Retrieves cached DataProfile from database or generates and caches it if missing."""
    existing_profile = db.query(DataProfile).filter(DataProfile.data_source_id == data_source.id).first()

    df = extract_dataframe_from_data_source(data_source)
    hist_profile = existing_profile.quality_scores if existing_profile else None
    profile_data = profile_dataframe(df, source_name=data_source.name, target_model_slug=target_model_slug, historical_profile=hist_profile)

    if existing_profile:
        existing_profile.summary = profile_data["summary"]
        existing_profile.column_profiles = profile_data["column_profiles"]
        existing_profile.quality_scores = profile_data["quality_scores"]
        db.commit()
        db.refresh(existing_profile)
        # Attach dynamic arrays for API serialization
        setattr(existing_profile, "quality_issues", profile_data.get("quality_issues", []))
        setattr(existing_profile, "findings", profile_data.get("findings", []))
        return existing_profile

    new_profile = DataProfile(
        data_source_id=data_source.id,
        organization_id=data_source.organization_id,
        summary=profile_data["summary"],
        column_profiles=profile_data["column_profiles"],
        quality_scores=profile_data["quality_scores"],
    )
    db.add(new_profile)
    db.commit()
    db.refresh(new_profile)
    # Attach dynamic arrays for API serialization
    setattr(new_profile, "quality_issues", profile_data.get("quality_issues", []))
    setattr(new_profile, "findings", profile_data.get("findings", []))
    return new_profile
