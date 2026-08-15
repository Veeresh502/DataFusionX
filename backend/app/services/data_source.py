import io
import json
import pandas as pd
import httpx
from typing import Dict, Any, Tuple
from sqlalchemy import create_engine, text
from fastapi import HTTPException, status


import math
import numpy as np


def sanitize_json_obj(obj: Any) -> Any:
    """Recursively replaces NaN, Inf, -Inf, and pandas/numpy scalar NaNs with None to ensure valid JSON."""
    if obj is None:
        return None
    if isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    try:
        if pd.isna(obj):
            return None
    except Exception:
        pass
    if isinstance(obj, (np.floating, np.integer)):
        val = obj.item()
        if isinstance(val, float) and (math.isnan(val) or math.isinf(val)):
            return None
        return val
    if isinstance(obj, dict):
        return {str(k): sanitize_json_obj(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [sanitize_json_obj(item) for item in obj]
    return obj


def _sanitize_preview_records(df: pd.DataFrame, max_rows: int = 20) -> list:
    """Converts top N rows of DataFrame into JSON-compatible python dicts, handling NaN/Inf values."""
    preview_df = df.head(max_rows).copy()
    records = preview_df.to_dict(orient="records")
    return sanitize_json_obj(records)


def _extract_dataframe_metadata(df: pd.DataFrame) -> Dict[str, Any]:
    """Generates standard metadata dictionary for tabular data including full records."""
    columns = list(df.columns)
    data_types = {str(col): str(dtype) for col, dtype in df.dtypes.items()}
    preview = _sanitize_preview_records(df, 20)
    all_records = sanitize_json_obj(df.to_dict(orient="records"))
    
    meta = {
        "row_count": int(len(df)),
        "column_count": int(len(columns)),
        "columns": [str(c) for c in columns],
        "data_types": data_types,
        "preview": preview,
        "records": all_records,
    }
    return sanitize_json_obj(meta)




def process_csv_bytes(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    if not filename.lower().endswith(".csv"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension must be .csv"
        )
    try:
        df = pd.read_csv(io.BytesIO(file_bytes))
        metadata = _extract_dataframe_metadata(df)
        metadata["filename"] = filename
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse CSV file: {str(e)}"
        )


def process_excel_bytes(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    if not (filename.lower().endswith(".xlsx") or filename.lower().endswith(".xls")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension must be .xlsx or .xls"
        )
    try:
        df = pd.read_excel(io.BytesIO(file_bytes))
        metadata = _extract_dataframe_metadata(df)
        metadata["filename"] = filename
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse Excel file: {str(e)}"
        )


def process_json_bytes(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    if not filename.lower().endswith(".json"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File extension must be .json"
        )
    try:
        data = json.loads(file_bytes.decode("utf-8"))
        if isinstance(data, list):
            df = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Try to normalize if it contains a list property, else single row
            list_keys = [k for k, v in data.items() if isinstance(v, list)]
            if list_keys:
                df = pd.DataFrame(data[list_keys[0]])
            else:
                df = pd.DataFrame([data])
        else:
            raise ValueError("JSON must contain an object or array of objects")

        metadata = _extract_dataframe_metadata(df)
        metadata["filename"] = filename
        return metadata
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to parse JSON dataset: {str(e)}"
        )


def test_rest_api_connection(
    url: str,
    method: str = "GET",
    headers: Dict[str, str] = None,
    auth_token: str = None
) -> Tuple[bool, str, Dict[str, Any]]:
    req_headers = headers.copy() if headers else {}
    if auth_token:
        req_headers["Authorization"] = f"Bearer {auth_token}"

    try:
        with httpx.Client(timeout=10.0, follow_redirects=True) as client:
            if method.upper() == "POST":
                res = client.post(url, headers=req_headers)
            else:
                res = client.get(url, headers=req_headers)

        if res.status_code >= 400:
            return False, f"HTTP Error {res.status_code}: {res.reason_phrase}", None

        # Try to parse response as JSON
        try:
            json_data = res.json()
            if isinstance(json_data, list):
                df = pd.DataFrame(json_data)
                meta = _extract_dataframe_metadata(df)
            elif isinstance(json_data, dict):
                df = pd.DataFrame([json_data])
                meta = _extract_dataframe_metadata(df)
            else:
                meta = {"raw_response": str(json_data)[:200]}
            return True, "REST API connection successful", meta
        except Exception:
            return True, f"HTTP {res.status_code} Success (Non-JSON response)", {"content_snippet": res.text[:200]}
            
    except Exception as e:
        return False, f"REST API Connection Failed: {str(e)}", None


def test_postgres_connection(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    schema_name: str = "public",
    table: str = None
) -> Tuple[bool, str, Dict[str, Any]]:
    db_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
    try:
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
            
            meta = {}
            if table:
                query = text(f'SELECT * FROM "{schema_name}"."{table}" LIMIT 20')
                df = pd.read_sql(query, conn)
                meta = _extract_dataframe_metadata(df)
                meta["table"] = table
                meta["schema"] = schema_name
                
        return True, "PostgreSQL connection successful", meta
    except Exception as e:
        return False, f"PostgreSQL Connection Failed: {str(e)}", None
