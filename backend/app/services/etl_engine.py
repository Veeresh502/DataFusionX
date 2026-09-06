import re
import time
import pandas as pd
import numpy as np
from datetime import datetime, timezone
from typing import Dict, Any, List, Tuple, Optional
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.data_source import DataSource
from app.models.pipeline import Pipeline
from app.models.pipeline_execution import PipelineExecution
from app.core.encryption import decrypt_credentials



def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class ETLLogger:
    def __init__(self):
        self.logs: List[Dict[str, Any]] = []

    def info(self, message: str):
        self.logs.append({"timestamp": _utc_now_iso(), "level": "INFO", "message": message})

    def warning(self, message: str):
        self.logs.append({"timestamp": _utc_now_iso(), "level": "WARNING", "message": message})

    def error(self, message: str):
        self.logs.append({"timestamp": _utc_now_iso(), "level": "ERROR", "message": message})


def extract_data(source: DataSource, logger: ETLLogger) -> pd.DataFrame:
    logger.info(f"Extract started for data source '{source.name}' ({source.type})")
    config = source.configuration or {}
    full_records = config.get("records") or config.get("all_records") or config.get("preview", [])



    if source.type in ["CSV", "EXCEL", "JSON"]:
        if full_records and isinstance(full_records, list):
            df = pd.DataFrame(full_records)
        else:
            df = pd.DataFrame()

    elif source.type == "REST_API":
        url = config.get("url")
        logger.info(f"Extracting data from REST API: {url}")
        if full_records and isinstance(full_records, list):
            df = pd.DataFrame(full_records)
        else:
            df = pd.DataFrame()


    elif source.type == "POSTGRESQL":
        host = config.get("host", "localhost")
        port = config.get("port", 5432)
        database = config.get("database")
        schema = config.get("schema", "public")
        table = config.get("table")
        
        creds = decrypt_credentials(source.encrypted_credentials) if source.encrypted_credentials else {}
        username = creds.get("username", "postgres")
        password = creds.get("password", "")

        db_url = f"postgresql://{username}:{password}@{host}:{port}/{database}"
        engine = create_engine(db_url, connect_args={"connect_timeout": 5})
        with engine.connect() as conn:
            query = text(f'SELECT * FROM "{schema}"."{table}"')
            df = pd.read_sql(query, conn)
    else:
        df = pd.DataFrame(full_records) if full_records and isinstance(full_records, list) else pd.DataFrame()

    logger.info(f"Records extracted: {len(df)} rows, {len(df.columns)} columns")

    return df


# --- TRANSFORMATIONS MODULE ---
def _resolve_col_name(df_cols: List[str], col_name: str) -> Optional[str]:
    """Safe case-insensitive column matching against DataFrame columns."""
    target = str(col_name).strip().lower()
    return next((c for c in df_cols if str(c).strip().lower() == target), None)


def validate_step_configuration(step: Dict[str, Any]) -> None:
    category = str(step.get("category") or "").lower()
    step_type = str(step.get("type") or step.get("step_type") or step.get("rule_type") or "").lower()

    if _is_validation_step(step):
        col = step.get("column")
        rule_type = str(step.get("rule_type") or step_type).upper()
        if not col or not str(col).strip():
            raise ValueError(f"Validation rule '{rule_type}' requires a target column.")
        if rule_type == "RANGE":
            min_val = step.get("min_val") if step.get("min_val") is not None else step.get("min_value")
            max_val = step.get("max_val") if step.get("max_val") is not None else step.get("max_value")
            if min_val is None and max_val is None:
                raise ValueError("RANGE validation rule requires at least a minimum or maximum value.")
        elif rule_type == "REGEX":
            pattern = step.get("pattern")
            if not pattern or not str(pattern).strip():
                raise ValueError("REGEX validation rule requires a regex pattern.")

    elif category == "transformation" or not _is_validation_step(step):
        if step_type == "filter_rows":
            cond = step.get("condition")
            if not cond or not str(cond).strip():
                raise ValueError("Filter Rows transformation requires a filter condition.")
        elif step_type in ["calculate_column", "derived_column"]:
            target_col = step.get("target_column") or step.get("column")
            formula = step.get("formula") or step.get("expression")
            if not target_col or not str(target_col).strip() or not formula or not str(formula).strip():
                raise ValueError("Calculate Column requires a destination column and formula expression.")
        elif step_type == "rename_columns":
            mapping = step.get("mapping")
            if not mapping or not isinstance(mapping, dict) or len(mapping) == 0:
                raise ValueError("Rename Columns requires at least one column mapping.")
        elif step_type == "change_data_types":
            mapping = step.get("mapping")
            if not mapping or not isinstance(mapping, dict) or len(mapping) == 0:
                raise ValueError("Change Data Types requires at least one data type mapping.")


def transform_dataframe(df: pd.DataFrame, steps: List[Dict[str, Any]], logger: ETLLogger) -> pd.DataFrame:
    logger.info("Transformation started")
    transformed_df = df.copy()

    for idx, step in enumerate(steps):
        validate_step_configuration(step)
        step_type = str(step.get("type") or step.get("step_type") or "").lower()
        logger.info(f"Applying transformation step {idx + 1}: {step_type}")


        if step_type == "remove_duplicates":
            cols = step.get("columns") if step.get("columns") is not None else step.get("subset")
            keep_val = step.get("keep", "first")
            if keep_val not in ["first", "last", False]:
                keep_val = "first"

            if not cols or len(cols) == 0:
                subset = None
            else:
                col_list = list(cols) if isinstance(cols, (list, tuple)) else [cols]
                subset = []
                for c in col_list:
                    matched = _resolve_col_name(transformed_df.columns, c)
                    if not matched:
                        err_msg = f"Column '{c}' configured for remove_duplicates does not exist in input dataset."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    subset.append(matched)

            transformed_df = transformed_df.drop_duplicates(subset=subset, keep=keep_val)

        elif step_type == "fill_null":
            fill_val = step.get("fill_value", "")
            columns = step.get("columns")
            if columns and isinstance(columns, list) and len(columns) > 0:
                for col in columns:
                    matched = _resolve_col_name(transformed_df.columns, col)
                    if not matched:
                        err_msg = f"Column '{col}' configured for fill_null does not exist in input dataset."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    transformed_df[matched] = transformed_df[matched].fillna(fill_val)
            else:
                transformed_df = transformed_df.fillna(fill_val)

        elif step_type == "drop_null":
            subset = step.get("columns")
            if subset and isinstance(subset, list) and len(subset) > 0:
                resolved_subset = []
                for col in subset:
                    matched = _resolve_col_name(transformed_df.columns, col)
                    if not matched:
                        err_msg = f"Column '{col}' configured for drop_null does not exist in input dataset."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    resolved_subset.append(matched)
                transformed_df = transformed_df.dropna(subset=resolved_subset)
            else:
                transformed_df = transformed_df.dropna()

        elif step_type == "trim_text":
            columns = step.get("columns")
            if columns and isinstance(columns, list) and len(columns) > 0:
                for col in columns:
                    matched = _resolve_col_name(transformed_df.columns, col)
                    if not matched:
                        err_msg = f"Column '{col}' configured for trim_text does not exist in input dataset."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    transformed_df[matched] = transformed_df[matched].apply(
                        lambda x: x.strip() if isinstance(x, str) else x
                    )
            else:
                for col in transformed_df.columns:
                    transformed_df[col] = transformed_df[col].apply(
                        lambda x: x.strip() if isinstance(x, str) else x
                    )

        elif step_type == "normalize_text":
            columns = step.get("columns")
            mode = str(step.get("mode", "lower")).lower()
            if columns and isinstance(columns, list) and len(columns) > 0:
                target_cols = []
                for col in columns:
                    matched = _resolve_col_name(transformed_df.columns, col)
                    if not matched:
                        err_msg = f"Column '{col}' configured for normalize_text does not exist in input dataset."
                        logger.error(err_msg)
                        raise ValueError(err_msg)
                    target_cols.append(matched)
            else:
                target_cols = list(transformed_df.columns)

            for col in target_cols:
                if mode == "lower":
                    transformed_df[col] = transformed_df[col].apply(lambda x: x.lower() if isinstance(x, str) else x)
                elif mode == "upper":
                    transformed_df[col] = transformed_df[col].apply(lambda x: x.upper() if isinstance(x, str) else x)
                elif mode == "title":
                    transformed_df[col] = transformed_df[col].apply(lambda x: x.title() if isinstance(x, str) else x)

        elif step_type == "rename_columns":
            column_map = step.get("mapping", {})
            resolved_map = {}
            for src_col, dst_col in column_map.items():
                matched = _resolve_col_name(transformed_df.columns, src_col)
                if not matched:
                    err_msg = f"Column '{src_col}' configured for rename_columns does not exist in input dataset."
                    logger.error(err_msg)
                    raise ValueError(err_msg)
                resolved_map[matched] = dst_col
            transformed_df = transformed_df.rename(columns=resolved_map)

        elif step_type == "change_data_types":
            type_map = step.get("mapping", {})
            for col, dtype in type_map.items():
                matched = _resolve_col_name(transformed_df.columns, col)
                if not matched:
                    err_msg = f"Column '{col}' configured for change_data_types does not exist in input dataset."
                    logger.error(err_msg)
                    raise ValueError(err_msg)
                try:
                    if dtype == "int":
                        transformed_df[matched] = pd.to_numeric(transformed_df[matched], errors="coerce").fillna(0).astype(int)
                    elif dtype == "float":
                        transformed_df[matched] = pd.to_numeric(transformed_df[matched], errors="coerce").astype(float)
                    elif dtype == "str":
                        transformed_df[matched] = transformed_df[matched].astype(str)
                    elif dtype == "datetime":
                        transformed_df[matched] = pd.to_datetime(transformed_df[matched], errors="coerce")
                except Exception as e:
                    err_msg = f"Failed to convert column '{col}' to {dtype}: {e}"
                    logger.error(err_msg)
                    raise ValueError(err_msg)

        elif step_type == "filter_rows":
            condition = step.get("condition")
            if not condition or not str(condition).strip():
                err_msg = "Filter condition is empty or missing."
                logger.error(err_msg)
                raise ValueError(err_msg)

            # Identify referenced columns in expression
            keywords = {"and", "or", "not", "in", "is", "true", "false", "none", "str", "int", "float", "len", "bool"}
            tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', str(condition))
            referenced_cols = [t for t in tokens if t.lower() not in keywords and not t.isdigit()]

            for ref in referenced_cols:
                matched = _resolve_col_name(transformed_df.columns, ref)
                if not matched:
                    err_msg = f"Column '{ref}' does not exist in input dataset."
                    logger.error(err_msg)
                    raise ValueError(err_msg)

            try:
                transformed_df = transformed_df.query(condition)
            except Exception as e:
                err_msg = f"Filter condition '{condition}' failed: {e}"
                logger.error(err_msg)
                raise ValueError(err_msg)

        elif step_type == "calculate_column" or step_type == "derived_column":
            target_col = step.get("target_column")
            formula = step.get("formula")
            if not target_col or not formula:
                err_msg = "Target column or formula missing for calculated column step."
                logger.error(err_msg)
                raise ValueError(err_msg)

            keywords = {"and", "or", "not", "in", "is", "true", "false", "none", "abs", "round", "sum", "min", "max", "len", "np", "pd"}
            tokens = re.findall(r'\b[a-zA-Z_][a-zA-Z0-9_]*\b', str(formula))
            referenced_cols = [t for t in tokens if t.lower() not in keywords and not t.isdigit()]

            for ref in referenced_cols:
                matched = _resolve_col_name(transformed_df.columns, ref)
                if not matched:
                    err_msg = f"Column '{ref}' referenced in formula '{formula}' does not exist in input dataset."
                    logger.error(err_msg)
                    raise ValueError(err_msg)

            try:
                transformed_df[target_col] = transformed_df.eval(formula)
            except Exception:
                try:
                    transformed_df[target_col] = transformed_df.apply(
                        lambda row: eval(formula, {}, row.to_dict()), axis=1
                    )
                except Exception as e:
                    err_msg = f"Failed to calculate derived column '{target_col}' with formula '{formula}': {e}"
                    logger.error(err_msg)
                    raise ValueError(err_msg)

    logger.info(f"Records transformed: {len(transformed_df)} rows remaining")
    return transformed_df



# --- VALIDATION MODULE ---
def validate_dataframe(df: pd.DataFrame, validation_rules: List[Dict[str, Any]], logger: ETLLogger) -> Tuple[pd.DataFrame, pd.DataFrame, List[str]]:
    logger.info("Validation started")
    if not validation_rules or df.empty:
        logger.info("Validation complete: 0 valid records, 0 invalid records")
        return df, pd.DataFrame(), []

    invalid_indices = set()
    errors = []

    for rule in validation_rules:
        rule_type = str(rule.get("rule_type") or rule.get("type") or "").upper()
        if "NOT_NULL" in rule_type or rule_type == "NOT_NULL":
            rule_type = "NOT_NULL"
        elif "UNIQUE" in rule_type or "PRIMARY_KEY" in rule_type or rule_type == "UNIQUE":
            rule_type = "UNIQUE"
        elif "RANGE" in rule_type or rule_type == "RANGE":
            rule_type = "RANGE"
        elif "REGEX" in rule_type or rule_type == "REGEX":
            rule_type = "REGEX"

        raw_col = rule.get("column") or rule.get("target_column")
        if not raw_col:
            errors.append(f"Validation rule '{rule_type}' missing target column configuration")
            logger.error(f"Validation rule '{rule_type}' missing column configuration")
            continue

        # Case-insensitive column matching
        col_match = next((c for c in df.columns if c.lower() == str(raw_col).lower()), None)
        if not col_match:
            err_msg = f"Validation Error: Column '{raw_col}' configured for rule '{rule_type}' is missing from dataset"
            errors.append(err_msg)
            logger.error(err_msg)
            continue

        col = col_match
        logger.info(f"Applying validation rule: {rule_type} -> {col}")

        if rule_type == "NOT_NULL":
            null_mask = df[col].isnull() | (df[col].astype(str).str.strip() == "") if df[col].dtype == object else df[col].isnull()
            failed_rows = df[null_mask]
            for idx in failed_rows.index:
                invalid_indices.add(idx)
                errors.append(f"Row {idx}: Column '{col}' violates NOT NULL constraint")

        elif rule_type == "UNIQUE" or rule_type == "PRIMARY_KEY":
            dup_mask = df.duplicated(subset=[col], keep=False)
            failed_rows = df[dup_mask]
            for idx in failed_rows.index:
                invalid_indices.add(idx)
                errors.append(f"Row {idx}: Column '{col}' violates UNIQUE constraint")

        elif rule_type == "RANGE":
            min_val = rule.get("min_val")
            max_val = rule.get("max_val")
            series = pd.to_numeric(df[col], errors="coerce")
            if min_val is not None:
                mask_min = series < min_val
                for idx in df[mask_min].index:
                    invalid_indices.add(idx)
                    errors.append(f"Row {idx}: Column '{col}' value is below min range {min_val}")
            if max_val is not None:
                mask_max = series > max_val
                for idx in df[mask_max].index:
                    invalid_indices.add(idx)
                    errors.append(f"Row {idx}: Column '{col}' value exceeds max range {max_val}")

        elif rule_type == "REGEX":
            pattern = rule.get("pattern")
            if pattern:
                try:
                    regex = re.compile(pattern)
                    for idx, val in df[col].items():
                        if pd.isnull(val) or not regex.search(str(val)):
                            invalid_indices.add(idx)
                            errors.append(f"Row {idx}: Column '{col}' value '{val}' violates REGEX pattern '{pattern}'")
                except Exception as e:
                    err_msg = f"Invalid REGEX pattern '{pattern}' for column '{col}': {e}"
                    errors.append(err_msg)
                    logger.error(err_msg)

    valid_df = df.drop(index=list(invalid_indices)) if invalid_indices else df.copy()
    invalid_df = df.loc[list(invalid_indices)] if invalid_indices else pd.DataFrame()

    if errors or len(invalid_df) > 0:
        logger.error(f"Validation failed: {len(invalid_df)} invalid records detected")
    else:
        logger.info(f"Validation rule passed")

    logger.info(f"Validation complete: {len(valid_df)} valid records, {len(invalid_df)} invalid records")
    return valid_df, invalid_df, errors


# --- LOAD MODULE ---
def load_data_to_postgres(df: pd.DataFrame, dest_config: Dict[str, Any], logger: ETLLogger, db: Optional[Session] = None) -> int:
    table_name = str(dest_config.get("table_name", "transformed_output")).strip()
    if_exists = dest_config.get("if_exists", "append")  # append, replace, fail
    dest_type = str(dest_config.get("destination_type", "")).upper()

    is_warehouse = (
        dest_type in ["WAREHOUSE", "WAREHOUSE_STAR_SCHEMA"]
        or table_name.lower() in ["fact_sales", "fact_production", "warehouse_star_schema", "sales_warehouse", "manufacturing_warehouse"]
    )

    if is_warehouse:
        model_id_val = dest_config.get("warehouse_model_id") or dest_config.get("warehouse_model_slug") or dest_config.get("warehouse_model") or "sales"
        logger.info(f"Load started: Target Data Warehouse model '{model_id_val}'")
        if not db:
            from app.db.session import SessionLocal
            db_session = SessionLocal()
            try:
                from app.services.warehouse import load_dataframe_to_warehouse
                loaded_count = load_dataframe_to_warehouse(db_session, df, model_id_val, dest_config)
            finally:
                db_session.close()
        else:
            from app.services.warehouse import load_dataframe_to_warehouse
            loaded_count = load_dataframe_to_warehouse(db, df, model_id_val, dest_config)

        logger.info(f"Load completed: {loaded_count} fact records loaded into Data Warehouse model '{model_id_val}'")
        return loaded_count

    else:
        logger.info(f"Load started: Flat target table '{table_name}' (mode: {if_exists})")
        conn = db.bind if db and hasattr(db, "bind") and db.bind else create_engine(settings.DATABASE_URL)
        inspector = inspect(conn)
        table_exists = inspector.has_table(table_name)
        
        if table_exists:
            if if_exists == "replace":
                conn.execute(text(f'DROP TABLE IF EXISTS "{table_name}"'))
                logger.info(f"Existing table '{table_name}' dropped (replace mode)")
            elif if_exists == "append":
                existing_cols = {c["name"] for c in inspector.get_columns(table_name)}
                for col in df.columns:
                    if col not in existing_cols:
                        sql_type = "VARCHAR"
                        if pd.api.types.is_integer_dtype(df[col]):
                            sql_type = "INTEGER"
                        elif pd.api.types.is_float_dtype(df[col]):
                            sql_type = "DOUBLE PRECISION"
                        elif pd.api.types.is_datetime64_any_dtype(df[col]):
                            sql_type = "TIMESTAMP WITH TIME ZONE"
                        elif pd.api.types.is_bool_dtype(df[col]):
                            sql_type = "BOOLEAN"
                        
                        conn.execute(text(f'ALTER TABLE "{table_name}" ADD COLUMN IF NOT EXISTS "{col}" {sql_type}'))
                        logger.info(f"Auto-added column '{col}' ({sql_type}) to target table '{table_name}'")

        df.to_sql(name=table_name, con=conn, if_exists=if_exists if if_exists != "replace" else "append", index=False)

        loaded_count = len(df)
        logger.info(f"Load completed: {loaded_count} records written to '{table_name}' table")
        return loaded_count


def _is_validation_step(s: Dict[str, Any]) -> bool:
    cat = str(s.get("category") or "").lower()
    tp = str(s.get("type") or s.get("node_type") or "").lower()
    rule_tp = str(s.get("rule_type") or "").lower()
    
    if cat == "validation" or cat == "val":
        return True
    if cat == "transformation":
        return False
        
    val_rules = ["not_null", "unique", "primary_key", "range", "regex"]
    return any(r in tp for r in val_rules) or any(r in rule_tp for r in val_rules)



# --- ETL EXECUTION ENGINE MANAGER ---
def run_pipeline(pipeline_id: int, db: Session) -> PipelineExecution:
    pipeline = db.query(Pipeline).filter(Pipeline.id == pipeline_id).first()
    if not pipeline:
        raise ValueError(f"Pipeline ID {pipeline_id} not found")

    logger = ETLLogger()
    start_time = time.time()
    
    execution = PipelineExecution(
        pipeline_id=pipeline.id,
        organization_id=pipeline.organization_id,
        status="RUNNING",
        started_at=datetime.now(timezone.utc),
        logs=[],
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)

    try:
        source = pipeline.source
        if not source:
            raise ValueError(f"Data source ID {pipeline.source_id} not found")

        # 1. EXTRACT
        t0 = time.time()
        extracted_df = extract_data(source, logger)
        t1 = time.time()
        execution.records_read = len(extracted_df)
        try:
            from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS, PIPELINE_RECORDS_READ_TOTAL
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="EXTRACT").observe(t1 - t0)
            PIPELINE_RECORDS_READ_TOTAL.inc(len(extracted_df))
        except Exception:
            pass

        # 2. TRANSFORM
        steps = pipeline.steps or []
        transform_steps = [s for s in steps if not _is_validation_step(s)]
        validation_steps = [s for s in steps if _is_validation_step(s)]

        t2 = time.time()
        try:
            transformed_df = transform_dataframe(extracted_df, transform_steps, logger)
        except Exception as tf_err:
            logger.error(f"Transformation failed: {str(tf_err)}")
            logger.info("Validation skipped because transformation failed")
            logger.info("Load skipped because transformation failed")
            execution.records_processed = 0
            execution.records_failed = 0
            execution.records_loaded = 0
            execution.status = "FAILED"
            execution.current_stage = "FAILED"
            execution.error = f"Transformation Failure: {str(tf_err)}"
            execution.completed_at = datetime.now(timezone.utc)
            execution.duration_seconds = round(time.time() - start_time, 3)
            execution.logs = logger.logs
            db.commit()
            return execution

        t3 = time.time()

        try:
            from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="TRANSFORM").observe(t3 - t2)
        except Exception:
            pass

        # 3. VALIDATE
        t4 = time.time()
        valid_df, invalid_df, validation_errors = validate_dataframe(transformed_df, validation_steps, logger)
        t5 = time.time()
        execution.records_processed = len(valid_df)
        execution.records_failed = len(invalid_df)
        try:
            from app.core.prometheus import (
                PIPELINE_STAGE_DURATION_SECONDS,
                PIPELINE_RECORDS_PROCESSED_TOTAL,
                PIPELINE_VALIDATION_ERRORS_TOTAL,
                PIPELINE_INVALID_RECORDS_TOTAL
            )
            PIPELINE_STAGE_DURATION_SECONDS.labels(stage="VALIDATE").observe(t5 - t4)
            PIPELINE_RECORDS_PROCESSED_TOTAL.inc(len(valid_df))
            if validation_errors:
                PIPELINE_VALIDATION_ERRORS_TOTAL.inc(len(validation_errors))
            if len(invalid_df) > 0:
                PIPELINE_INVALID_RECORDS_TOTAL.inc(len(invalid_df))
        except Exception:
            pass

        # 4. LOAD & STRICT LOAD PROTECTION
        if validation_errors or len(invalid_df) > 0:
            execution.records_loaded = 0
            execution.status = "FAILED"
            execution.current_stage = "FAILED"
            err_summary = validation_errors[0] if validation_errors else f"Validation failed with {len(invalid_df)} invalid records."
            execution.error = f"Validation Failure: {err_summary}"
            logger.error(f"Pipeline execution failed due to validation errors: {err_summary}")
            logger.info("Load skipped: Validation failed")

        else:
            t6 = time.time()
            if not valid_df.empty and pipeline.destination_config:
                loaded_count = load_data_to_postgres(valid_df, pipeline.destination_config, logger, db=db)
                execution.records_loaded = loaded_count
            else:
                execution.records_loaded = 0
                logger.info("Load skipped: No valid records to write or destination omitted")
            t7 = time.time()
            try:
                from app.core.prometheus import PIPELINE_STAGE_DURATION_SECONDS, PIPELINE_RECORDS_LOADED_TOTAL
                PIPELINE_STAGE_DURATION_SECONDS.labels(stage="LOAD").observe(t7 - t6)
                PIPELINE_RECORDS_LOADED_TOTAL.inc(execution.records_loaded)
            except Exception:
                pass

            execution.status = "SUCCESS"

    except Exception as e:
        logger.error(f"Pipeline execution failed: {str(e)}")
        execution.status = "FAILED"
        execution.error = str(e)


    finally:
        end_time = time.time()
        execution.completed_at = datetime.now(timezone.utc)
        duration = round(end_time - start_time, 3)
        execution.duration_seconds = duration
        execution.logs = logger.logs
        db.commit()
        db.refresh(execution)

        # Update Prometheus Pipeline Execution Metrics
        try:
            from app.core.prometheus import (
                PIPELINE_EXECUTIONS_TOTAL,
                PIPELINE_EXECUTION_DURATION_SECONDS,
                PIPELINE_FAILURES_TOTAL,
                PIPELINE_THROUGHPUT
            )
            dest_type = (pipeline.destination_config or {}).get("destination_type", "POSTGRES")
            trig_type = getattr(execution, "trigger_type", "MANUAL")
            
            PIPELINE_EXECUTIONS_TOTAL.labels(status=execution.status, trigger_type=trig_type, destination_type=dest_type).inc()
            PIPELINE_EXECUTION_DURATION_SECONDS.labels(status=execution.status, trigger_type=trig_type).observe(duration)
            
            if execution.status == "FAILED":
                PIPELINE_FAILURES_TOTAL.inc()
            
            if duration > 0 and (execution.records_processed or 0) > 0:
                PIPELINE_THROUGHPUT.set(round(execution.records_processed / duration, 2))
        except Exception:
            pass

    return execution

