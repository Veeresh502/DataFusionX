import math
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session

from app.models.data_source import DataSource
from app.models.data_profile import DataProfile


def _clean_val(val: Any) -> Any:
    """Helper to sanitize numpy/pandas scalar values for JSON serialization."""
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


def profile_dataframe(df: pd.DataFrame) -> Dict[str, Any]:
    """Generates structured profiling metrics for a Pandas DataFrame."""
    total_rows = int(len(df))
    columns = list(df.columns)
    total_cols = int(len(columns))
    
    # Handle empty dataset
    if total_rows == 0:
        return {
            "summary": {
                "row_count": 0,
                "column_count": total_cols,
                "duplicate_rows": 0,
                "memory_bytes": 0,
            },
            "column_profiles": [],
            "quality_scores": {
                "completeness": 0.0,
                "uniqueness": 0.0,
                "validity": 0.0,
                "overall": 0.0,
            }
        }

    duplicate_rows = int(df.duplicated().sum())
    memory_bytes = int(df.memory_usage(deep=True).sum())

    column_profiles = []
    total_nulls = 0
    total_cells = total_rows * total_cols

    for col in columns:
        series = df[col]
        null_count = int(series.isnull().sum())
        total_nulls += null_count
        null_pct = round((null_count / total_rows) * 100, 2)
        unique_count = int(series.nunique(dropna=True))
        unique_pct = round((unique_count / total_rows) * 100, 2)

        raw_dtype = str(series.dtype)
        col_prof: Dict[str, Any] = {
            "name": str(col),
            "data_type": raw_dtype,
            "null_count": null_count,
            "null_percentage": null_pct,
            "unique_count": unique_count,
            "unique_percentage": unique_pct,
        }

        # Check if numeric column
        if pd.api.types.is_numeric_dtype(series) and not pd.api.types.is_bool_dtype(series):
            non_null = series.dropna()
            if not non_null.empty:
                q1 = float(non_null.quantile(0.25))
                q3 = float(non_null.quantile(0.75))
                iqr = q3 - q1
                lower_bound = q1 - (1.5 * iqr)
                upper_bound = q3 + (1.5 * iqr)
                
                outliers_series = non_null[(non_null < lower_bound) | (non_null > upper_bound)]
                outlier_vals = [_clean_val(v) for v in outliers_series.head(10).tolist()]

                col_prof["min"] = _clean_val(non_null.min())
                col_prof["max"] = _clean_val(non_null.max())
                col_prof["mean"] = _clean_val(non_null.mean())
                col_prof["median"] = _clean_val(non_null.median())
                col_prof["std"] = _clean_val(non_null.std()) if len(non_null) > 1 else 0.0
                col_prof["outlier_count"] = int(len(outliers_series))
                col_prof["outliers"] = outlier_vals

        # Check if date/datetime column
        is_date_col = False
        if pd.api.types.is_datetime64_any_dtype(series):
            is_date_col = True
            date_series = series.dropna()
        else:
            # Try parsing as datetime if column contains strings resembling dates
            if raw_dtype == "object" or raw_dtype == "string":
                try:
                    parsed_dates = pd.to_datetime(series.dropna(), errors="coerce", format="mixed")
                    if parsed_dates.notnull().sum() > (len(series.dropna()) * 0.7) and len(parsed_dates.dropna()) > 0:
                        is_date_col = True
                        date_series = parsed_dates.dropna()
                except Exception:
                    pass

        if is_date_col and 'date_series' in locals() and not date_series.empty:
            col_prof["min_date"] = str(date_series.min())
            col_prof["max_date"] = str(date_series.max())
            
            # Distribution over time (group by month/year)
            try:
                dist_df = date_series.dt.to_period("M").value_counts().sort_index().reset_index()
                dist_df.columns = ["period", "count"]
                col_prof["date_distribution"] = [
                    {"period": str(row["period"]), "count": int(row["count"])}
                    for _, row in dist_df.head(12).iterrows()
                ]
            except Exception:
                col_prof["date_distribution"] = []

        # Categorical Stats (if object/string/categorical or low cardinality numeric)
        if not pd.api.types.is_numeric_dtype(series) or unique_count <= 10:
            col_prof["cardinality"] = unique_count
            top_counts = series.value_counts(dropna=True).head(5)
            col_prof["top_values"] = [
                {
                    "value": _clean_val(val),
                    "count": int(cnt),
                    "percentage": round((cnt / total_rows) * 100, 2)
                }
                for val, cnt in top_counts.items()
            ]

        column_profiles.append(col_prof)

    # Quality Scores Calculation
    completeness = round(((total_cells - total_nulls) / total_cells) * 100, 2) if total_cells > 0 else 0.0
    uniqueness = round(((total_rows - duplicate_rows) / total_rows) * 100, 2) if total_rows > 0 else 0.0
    validity = 100.0  # Default validity score for clean ingested table
    overall_quality = round((completeness * 0.4) + (uniqueness * 0.4) + (validity * 0.2), 2)

    return {
        "summary": {
            "row_count": total_rows,
            "column_count": total_cols,
            "duplicate_rows": duplicate_rows,
            "memory_bytes": memory_bytes,
        },
        "column_profiles": column_profiles,
        "quality_scores": {
            "completeness": completeness,
            "uniqueness": uniqueness,
            "validity": validity,
            "overall": overall_quality,
        }
    }


def get_or_create_data_profile(data_source: DataSource, db: Session) -> DataProfile:
    """Retrieves cached DataProfile from database or generates and caches it if missing."""
    existing_profile = db.query(DataProfile).filter(DataProfile.data_source_id == data_source.id).first()
    if existing_profile:
        return existing_profile

    # Generate profile from configuration preview or DataFrame
    config = data_source.configuration or {}
    preview_data = config.get("preview", [])
    
    if preview_data and isinstance(preview_data, list):
        df = pd.DataFrame(preview_data)
    else:
        df = pd.DataFrame()

    profile_data = profile_dataframe(df)

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
    return new_profile
