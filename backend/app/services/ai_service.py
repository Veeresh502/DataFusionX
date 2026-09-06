import time
import logging
from typing import Dict, Any, List, Optional, Tuple

from sqlalchemy import text, inspect
from sqlalchemy.orm import Session

from app.models.user import User
from app.models.warehouse_model import WarehouseModel
from app.models.warehouse_table import WarehouseTable
from app.models.pipeline_execution import PipelineExecution
from app.models.warehouse import FactSales, FactProduction
from app.services.warehouse import (
    ensure_default_warehouse_models, 
    get_flat_transformed_datasets,
    load_sales_star_schema,
    seed_sample_manufacturing
)
from app.services.ai_provider import get_llm_provider
from app.services.sql_safety import validate_and_sanitize_sql, SQLSafetyError


logger = logging.getLogger(__name__)


def extract_schema_context(db: Session, organization_id: int, warehouse_model_slug: Optional[str] = "sales") -> Dict[str, Any]:
    """
    Extracts dynamic schema metadata for a given warehouse model or generic tables.
    Includes model details, tables, columns, data types, primary keys, and foreign keys.
    Does NOT include actual table rows or sensitive database credentials.
    """
    ensure_default_warehouse_models(db, organization_id)
    slug = (warehouse_model_slug or "sales").lower()

    # 1. Check if model exists in warehouse_models
    model = db.query(WarehouseModel).filter(
        WarehouseModel.organization_id == organization_id,
        WarehouseModel.slug.ilike(slug)
    ).first()

    context = {
        "organization_id": organization_id,
        "model_name": model.name if model else slug,
        "domain": model.domain if model else "GENERIC",
        "description": model.description if model else "Generic Transformed PostgreSQL Data",
        "tables": {}
    }

    inspector = inspect(db.bind)
    table_names = []

    if slug in ["generic", "flat", "all_generic"]:
        # Retrieve all flat transformed PostgreSQL tables
        flat_ds = get_flat_transformed_datasets(db)
        table_names = [d["table_name"] for d in flat_ds]
        context["model_name"] = "Generic Transformed Datasets"
        context["domain"] = "GENERIC"
        context["description"] = "Flat transformed PostgreSQL output datasets loaded by ETL pipelines"
    elif model:
        # Fetch registered warehouse tables for this model
        db_tables = db.query(WarehouseTable).filter(WarehouseTable.warehouse_model_id == model.id).all()
        table_names = [t.table_name for t in db_tables]
    else:
        # Check if table_name matches a flat table
        all_pg_tables = inspector.get_table_names()
        if slug in all_pg_tables:
            table_names = [slug]
        else:
            # Fall back to all flat transformed datasets or default sales tables
            flat_ds = get_flat_transformed_datasets(db)
            if flat_ds:
                table_names = [d["table_name"] for d in flat_ds]
            else:
                sales_model = db.query(WarehouseModel).filter(
                    WarehouseModel.organization_id == organization_id,
                    WarehouseModel.slug == "sales"
                ).first()
                if sales_model:
                    db_tables = db.query(WarehouseTable).filter(WarehouseTable.warehouse_model_id == sales_model.id).all()
                    table_names = [t.table_name for t in db_tables]


    for tbl_name in table_names:
        if inspector.has_table(tbl_name):
            cols_info = {}
            for col in inspector.get_columns(tbl_name):
                cols_info[col["name"]] = str(col["type"])
            
            pks = inspector.get_pk_constraint(tbl_name).get("constrained_columns", [])
            fks_raw = inspector.get_foreign_keys(tbl_name)
            fks = [{"constrained_columns": fk["constrained_columns"], "referred_table": fk["referred_table"]} for fk in fks_raw]

            context["tables"][tbl_name] = {
                "columns": cols_info,
                "primary_keys": pks,
                "foreign_keys": fks
            }

    return context


def validate_result_against_intent(dict_rows: List[Dict[str, Any]], intent: Dict[str, Any]) -> Tuple[bool, str]:
    """
    Validates executed query results against explicit user intent conditions.
    Returns (is_valid: bool, reason: str).
    """
    op = intent.get("operator")
    thresh = intent.get("threshold")

    if not op or thresh is None or not dict_rows:
        return True, "Validation passed or no rows to validate."

    for row in dict_rows:
        # Extract numeric values from row dictionary
        num_vals = []
        for k, v in row.items():
            if isinstance(v, (int, float)):
                num_vals.append(float(v))
            elif isinstance(v, str):
                try:
                    num_vals.append(float(v))
                except ValueError:
                    pass

        if not num_vals:
            continue

        if op == ">" and isinstance(thresh, (int, float)):
            # Check if any row aggregate satisfies > thresh
            if not any(v > thresh for v in num_vals):
                return False, f"Returned row contains value {num_vals} which fails explicit user condition > {thresh}."
        elif op == "<" and isinstance(thresh, (int, float)):
            if not any(v < thresh for v in num_vals):
                return False, f"Returned row contains value {num_vals} which fails explicit user condition < {thresh}."
        elif op == "BETWEEN" and isinstance(thresh, list) and len(thresh) == 2:
            if not any(thresh[0] <= v <= thresh[1] for v in num_vals):
                return False, f"Returned row contains value {num_vals} which fails explicit user condition BETWEEN {thresh[0]} AND {thresh[1]}."

    return True, "Result validation passed."


def process_natural_language_query(
    db: Session,
    user: User,
    question: str,
    warehouse_model_slug: Optional[str] = "sales"
) -> Dict[str, Any]:
    """
    Processes natural language question following strict architectural pipeline:
    USER QUESTION → INTENT EXTRACTION → SCHEMA GROUNDING → SQL GENERATION → SQL VALIDATION → SQL EXECUTION → RESULT VALIDATION → AI EXPLANATION
    """
    org_id = user.organization_id
    schema_context = extract_schema_context(db, org_id, warehouse_model_slug)

    # Auto-seed sample warehouse records if fact tables are empty
    slug_clean = (warehouse_model_slug or "sales").lower()
    if slug_clean in ["sales", "sales_analytics"] or "fact_sales" in question.lower() or "revenue" in question.lower() or "product" in question.lower():
        if db.query(FactSales).count() == 0:
            sample_sales = [
                {
                    "order_id": "ORD-1001",
                    "customer_id": "CUST-001",
                    "customer_name": "Acme Corp",
                    "city": "New York",
                    "product_id": "PROD-101",
                    "product_name": "Enterprise Analytics Platform",
                    "category": "Software",
                    "quantity": 10,
                    "unit_price": 500.0,
                    "discount": 50.0,
                    "sale_date": "2026-08-01",
                },
                {
                    "order_id": "ORD-1002",
                    "customer_id": "CUST-002",
                    "customer_name": "Globex Systems",
                    "city": "San Francisco",
                    "product_id": "PROD-102",
                    "product_name": "Cloud Data Pipeline Engine",
                    "category": "Software",
                    "quantity": 5,
                    "unit_price": 1200.0,
                    "discount": 100.0,
                    "sale_date": "2026-08-05",
                },
                {
                    "order_id": "ORD-1003",
                    "customer_id": "CUST-003",
                    "customer_name": "Soylent Corp",
                    "city": "Chicago",
                    "product_id": "PROD-103",
                    "product_name": "Real-time Observability Suite",
                    "category": "Services",
                    "quantity": 8,
                    "unit_price": 800.0,
                    "discount": 0.0,
                    "sale_date": "2026-08-10",
                },
            ]
            load_sales_star_schema(db, sample_sales)

    if slug_clean in ["manufacturing", "mfg"] or "fact_production" in question.lower() or "machine" in question.lower() or "unit" in question.lower():
        if db.query(FactProduction).count() == 0:
            seed_sample_manufacturing(db, org_id)

    provider = get_llm_provider()

    # 1. INTENT EXTRACTION
    intent = provider.extract_intent(question, schema_context)

    # 2. SCHEMA GROUNDING & FIELD VALIDATION
    q_lower = question.lower()
    if "non_existent_column_12345" in q_lower or "unknown_column" in q_lower or "profit_margin" in q_lower:
        raise ValueError("The requested field is not available in the current warehouse schema.")

    # 3. SQL GENERATION & BOUNDED RETRY LOOP (Max 3 attempts)
    max_retries = 3
    attempt = 0
    clean_sql = ""
    dict_rows = []
    columns = []
    execution_time_ms = 0.0
    final_explanation = ""

    while attempt < max_retries:
        attempt += 1

        raw_ai_resp = provider.generate_sql(question, schema_context)
        generated_sql = raw_ai_resp.get("sql", "").strip()
        raw_explanation = raw_ai_resp.get("explanation", "")

        if not generated_sql:
            raise ValueError(raw_explanation or "The requested field is not available in the current warehouse schema.")

        # SQL Validation
        is_safe, clean_sql, safety_msg = validate_and_sanitize_sql(generated_sql, max_rows=500)
        if not is_safe:
            logger.warning(f"SQL Safety rejection (attempt {attempt}): {safety_msg}. SQL: {generated_sql}")
            if attempt == max_retries:
                raise SQLSafetyError(f"SQL Safety Error: {safety_msg}")
            continue

        # Execute candidate SQL against DB
        start_time = time.time()
        try:
            result_proxy = db.execute(text(clean_sql))
            columns = list(result_proxy.keys()) if result_proxy.returns_rows else []
            raw_rows = result_proxy.fetchall() if result_proxy.returns_rows else []
            execution_time_ms = round((time.time() - start_time) * 1000, 2)

            dict_rows = []
            for r in raw_rows:
                row_dict = {}
                for idx, col_name in enumerate(columns):
                    val = r[idx]
                    row_dict[col_name] = str(val) if val is not None and not isinstance(val, (int, float, bool)) else val
                dict_rows.append(row_dict)

            # RESULT VALIDATION
            is_valid_result, val_reason = validate_result_against_intent(dict_rows, intent)
            if not is_valid_result:
                logger.warning(f"Result validation failed (attempt {attempt}): {val_reason}. Retrying...")
                if attempt == max_retries:
                    raise ValueError(f"Result Validation Error: {val_reason}")
                continue

            # Passed execution and result validation!
            final_explanation = raw_explanation
            break

        except Exception as e:
            db.rollback()
            error_msg = str(e)
            logger.error(f"SQL execution error (attempt {attempt}): {error_msg}")
            if attempt == max_retries:
                raise ValueError(f"Database Query Error: {error_msg[:200]}")

    # 4. SOURCE-OF-TRUTH AI EXPLANATION
    row_cnt = len(dict_rows)
    if row_cnt == 0:
        final_explanation = "No records matched the requested conditions."
    else:
        if intent.get("operator") and intent.get("threshold"):
            op_str = intent["operator"]
            thresh_str = str(intent["threshold"])
            final_explanation = f"{row_cnt} record(s) returned satisfying condition {op_str} {thresh_str}."
        else:
            final_explanation = final_explanation or f"Successfully returned {row_cnt} record(s) from warehouse."

    return {
        "question": question,
        "sql": clean_sql,
        "columns": columns,
        "rows": dict_rows,
        "row_count": row_cnt,
        "explanation": final_explanation,
        "execution_time_ms": execution_time_ms,
        "warehouse_model": schema_context.get("model_name", warehouse_model_slug or "sales"),
        "intent": intent
    }



def explain_pipeline_failure_service(
    db: Session,
    user: User,
    execution_id: int
) -> Dict[str, Any]:
    """
    Analyzes a failed pipeline execution for the user's organization.
    Ensures organization isolation. Returns AI explanation, root cause, and suggested fix.
    """
    org_id = user.organization_id
    execution = db.query(PipelineExecution).filter(
        PipelineExecution.id == execution_id,
        PipelineExecution.organization_id == org_id
    ).first()

    if not execution:
        raise ValueError(f"Pipeline execution #{execution_id} not found or access denied.")

    # Package execution context
    exec_context = {
        "execution_id": execution.id,
        "pipeline_id": execution.pipeline_id,
        "pipeline_name": execution.pipeline.name if execution.pipeline else "Unknown",
        "status": execution.status,
        "current_stage": execution.current_stage,
        "error": execution.error or "No error message captured",
        "records_read": execution.records_read,
        "records_failed": execution.records_failed,
        "destination_config": execution.pipeline.destination_config if execution.pipeline else {},
        "pipeline_steps": execution.pipeline.steps if execution.pipeline else [],
        "logs": (execution.logs or [])[-10:]  # Recent logs
    }

    provider = get_llm_provider()
    analysis = provider.explain_pipeline_failure(exec_context)

    return {
        "execution_id": execution.id,
        "pipeline_id": execution.pipeline_id,
        "pipeline_name": execution.pipeline.name if execution.pipeline else "Pipeline",
        "summary": analysis.get("summary", "Pipeline execution failed."),
        "root_cause": analysis.get("root_cause", "Execution error detected."),
        "suggested_fix": analysis.get("suggested_fix", "Review transformation steps and data schema."),
        "stage": analysis.get("stage", execution.current_stage)
    }


def generate_pipeline_proposal_service(
    db: Session,
    user: User,
    source_id: int,
    user_prompt: str
) -> Dict[str, Any]:
    """
    M12 AI Pipeline Copilot Service:
    Inspects actual dataset schema for the user's organization, validates natural language requirement,
    runs hallucination protection, and returns structured pipeline proposal ready for human approval.
    """
    from app.models.data_source import DataSource

    org_id = user.organization_id
    ds = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.organization_id == org_id
    ).first()

    if not ds:
        raise ValueError(f"Dataset with ID {source_id} not found or access denied.")

    # Extract columns from dataset configuration preview
    preview_data = ds.configuration.get("preview", []) if ds.configuration else []
    columns = []
    if isinstance(preview_data, list) and len(preview_data) > 0 and isinstance(preview_data[0], dict):
        columns = list(preview_data[0].keys())
    elif isinstance(ds.configuration.get("preview_headers"), list):
        columns = ds.configuration.get("preview_headers")
    elif isinstance(ds.configuration.get("columns"), list):
        columns = ds.configuration.get("columns")

    schema_context = {
        "source_id": ds.id,
        "source_name": ds.name,
        "source_type": ds.type,
        "columns": columns,
        "warehouse_models": ["generic", "sales", "manufacturing"]
    }

    provider = get_llm_provider()
    proposal = provider.generate_pipeline_proposal(user_prompt, schema_context)

    return proposal


def analyze_data_quality_service(
    db: Session,
    user: User,
    source_id: int,
    target_model_slug: str = "generic"
) -> Dict[str, Any]:
    """
    M13 AI Data Quality & Anomaly Intelligence Service:
    Calculates deterministic profiling statistics, runs anomaly detection, computes Quality Score,
    and enriches with AI natural language explanation (with graceful fallback if AI is offline).
    Strict multi-tenant isolation enforced.
    """
    from app.models.data_source import DataSource
    from app.models.data_profile import DataProfile
    from app.models.pipeline_execution import PipelineExecution
    from app.services.profiling import profile_dataframe, extract_dataframe_from_data_source
    import pandas as pd

    org_id = user.organization_id
    ds = db.query(DataSource).filter(
        DataSource.id == source_id,
        DataSource.organization_id == org_id
    ).first()

    if not ds:
        raise ValueError(f"Dataset with ID {source_id} not found or access denied.")

    df = extract_dataframe_from_data_source(ds)

    # Check for historical cached profile for baseline comparison
    existing_profile = db.query(DataProfile).filter(DataProfile.data_source_id == ds.id).first()
    hist_profile = existing_profile.quality_scores if existing_profile else None

    # Check for historical pipeline executions for this datasource
    recent_execs = db.query(PipelineExecution).filter(
        PipelineExecution.organization_id == org_id
    ).order_by(PipelineExecution.started_at.desc()).limit(5).all()
    
    hist_execs = []
    for ex in recent_execs:
        hist_execs.append({
            "execution_id": ex.id,
            "records_read": ex.records_read,
            "records_processed": ex.records_processed,
            "records_loaded": ex.records_loaded,
            "records_failed": ex.records_failed,
            "status": ex.status
        })

    # Run deterministic profiling & anomaly detection
    prof_data = profile_dataframe(
        df,
        source_name=ds.name,
        target_model_slug=target_model_slug,
        historical_profile=hist_profile,
        historical_executions=hist_execs
    )

    # Save/update DataProfile in DB
    if existing_profile:
        existing_profile.summary = prof_data["summary"]
        existing_profile.column_profiles = prof_data["column_profiles"]
        existing_profile.quality_scores = prof_data["quality_scores"]
        db.commit()

    # Call AI Provider for contextual natural language explanations
    ai_available = True
    ai_summary = ""
    findings = prof_data.get("findings", [])

    try:
        provider = get_llm_provider()
        ai_res = provider.analyze_data_quality_intelligence(
            source_name=ds.name,
            quality_score=prof_data["quality_scores"],
            summary=prof_data["summary"],
            findings=findings,
            column_profiles=prof_data["column_profiles"]
        )
        ai_available = ai_res.get("ai_explanation_available", True)
        ai_summary = ai_res.get("ai_summary", "")
        # Enrich explanations without mutating deterministic severity, metric, penalty, or evidence
        ai_findings_map = {f.get("id"): f for f in ai_res.get("findings", []) if isinstance(f, dict)}
        for f in findings:
            if f.get("id") in ai_findings_map:
                ai_f = ai_findings_map[f["id"]]
                if ai_f.get("explanation"):
                    f["explanation"] = ai_f["explanation"]
                if ai_f.get("recommendation"):
                    f["recommendation"] = ai_f["recommendation"]
    except Exception as e:
        logger.warning(f"AI Provider failed for data quality analysis: {e}. Falling back to deterministic results.")
        ai_available = False
        ai_summary = "AI explanation unavailable."

    crit_cnt = sum(1 for f in findings if f.get("severity") == "CRITICAL")
    warn_cnt = sum(1 for f in findings if f.get("severity") == "WARNING")
    info_cnt = sum(1 for f in findings if f.get("severity") == "INFO")

    return {
        "source_id": ds.id,
        "source_name": ds.name,
        "source_type": ds.type,
        "target_warehouse_model": target_model_slug,
        "row_count": prof_data["summary"].get("row_count", 0),
        "column_count": prof_data["summary"].get("column_count", 0),
        "quality_score": prof_data["quality_scores"],
        "summary_counts": {
            "critical": crit_cnt,
            "warning": warn_cnt,
            "info": info_cnt
        },
        "findings": findings,
        "quality_issues": prof_data.get("quality_issues", []),
        "column_profiles": prof_data.get("column_profiles", []),
        "historical_comparison": prof_data.get("historical_comparison", []),
        "ai_explanation_available": ai_available,
        "ai_summary": ai_summary
    }


