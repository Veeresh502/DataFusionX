import time
import logging
from typing import Dict, Any, List, Optional
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


def process_natural_language_query(
    db: Session,
    user: User,
    question: str,
    warehouse_model_slug: Optional[str] = "sales"
) -> Dict[str, Any]:
    """
    Processes natural language question:
    1. Extracts schema context for user's organization.
    2. Sends prompt to LLM Provider.
    3. Validates generated SQL through SQL Safety Engine.
    4. Executes safe SELECT query against DB.
    5. Returns structured JSON with query results and explanation.
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

    # 1. Ask LLM to generate SQL & explanation
    provider = get_llm_provider()

    raw_ai_resp = provider.generate_sql(question, schema_context)

    generated_sql = raw_ai_resp.get("sql", "").strip()
    explanation = raw_ai_resp.get("explanation", "")

    if not generated_sql:
        raise ValueError(explanation or "The requested dataset, table, or entity is not present in the selected warehouse model context.")


    # 2. Validate SQL Safety (Strict Read-Only SELECT check)
    is_safe, clean_sql, safety_msg = validate_and_sanitize_sql(generated_sql, max_rows=100)
    if not is_safe:
        logger.warning(f"SQL Safety rejection for user {user.email}: {safety_msg}. Generated SQL: {generated_sql}")
        raise SQLSafetyError(f"SQL Safety Error: {safety_msg}")

    # 3. Execute Read-Only Query against PostgreSQL with timing
    start_time = time.time()
    try:
        result_proxy = db.execute(text(clean_sql))
        columns = list(result_proxy.keys()) if result_proxy.returns_rows else []
        raw_rows = result_proxy.fetchall() if result_proxy.returns_rows else []
        execution_time_ms = round((time.time() - start_time) * 1000, 2)

        # Convert rows to serializable dicts
        dict_rows = []
        for r in raw_rows:
            row_dict = {}
            for idx, col_name in enumerate(columns):
                val = r[idx]
                row_dict[col_name] = str(val) if val is not None and not isinstance(val, (int, float, bool)) else val
            dict_rows.append(row_dict)

        return {
            "question": question,
            "sql": clean_sql,
            "columns": columns,
            "rows": dict_rows,
            "row_count": len(dict_rows),
            "explanation": explanation,
            "execution_time_ms": execution_time_ms,
            "warehouse_model": schema_context.get("model_name", warehouse_model_slug or "sales")
        }

    except Exception as e:
        db.rollback()
        error_msg = str(e)
        logger.error(f"Failed to execute AI-generated SQL query: {error_msg}")
        raise ValueError(f"Database Query Error: Unable to execute generated query. Details: {error_msg[:200]}")


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
