from typing import List, Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.user import User
from app.schemas.warehouse import (
    WarehouseTableSummary,
    WarehouseTableDetail,
    RevenueMetrics,
    WarehouseModelOut,
    WarehouseTableOut,
    GenericWarehouseAnalytics,
    ManufacturingMetrics,
)
from app.services.warehouse import (
    get_warehouse_models_list,
    get_warehouse_model_by_identifier,
    get_generic_model_analytics,
    get_manufacturing_analytics,
    seed_sample_manufacturing,
    clear_warehouse_manufacturing_data,
    get_warehouse_tables_summary,
    get_flat_transformed_datasets,
    get_warehouse_table_detail,
    get_warehouse_analytics,
    load_sales_star_schema,
    clear_warehouse_sales_data,
)
from app.api.deps import get_current_user, RoleChecker

router = APIRouter()

require_write_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER"])
require_read_access = RoleChecker(allowed_roles=["ADMIN", "DATA_ENGINEER", "ANALYST", "VIEWER"])


# --- GENERIC WAREHOUSE MODEL ENDPOINTS ---
@router.get("/models", response_model=List[WarehouseModelOut])
def list_warehouse_models(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[WarehouseModelOut]:
    return get_warehouse_models_list(db, current_user.organization_id)


@router.get("/models/{model_id_or_slug}", response_model=WarehouseModelOut)
def get_warehouse_model_detail(
    model_id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> WarehouseModelOut:
    try:
        return get_warehouse_model_by_identifier(db, model_id_or_slug, current_user.organization_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/models/{model_id_or_slug}/tables", response_model=List[WarehouseTableSummary])
def get_model_tables_summary(
    model_id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[WarehouseTableSummary]:
    try:
        wm = get_warehouse_model_by_identifier(db, model_id_or_slug, current_user.organization_id)
        return get_warehouse_tables_summary(db, model_slug_or_id=wm.slug)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/models/{model_id_or_slug}/analytics", response_model=GenericWarehouseAnalytics)
def get_model_generic_analytics(
    model_id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> GenericWarehouseAnalytics:
    try:
        wm = get_warehouse_model_by_identifier(db, model_id_or_slug, current_user.organization_id)
        return get_generic_model_analytics(db, wm)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.get("/models/{model_id_or_slug}/sales-analytics", response_model=RevenueMetrics)
def get_model_sales_analytics(
    model_id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> RevenueMetrics:
    wm = get_warehouse_model_by_identifier(db, model_id_or_slug, current_user.organization_id)
    if wm.slug.lower() not in ["sales", "sales_analytics"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse model '{wm.name}' is domain '{wm.domain}', not SALES domain"
        )
    return get_warehouse_analytics(db)


@router.get("/models/{model_id_or_slug}/manufacturing-analytics", response_model=ManufacturingMetrics)
def get_model_manufacturing_analytics(
    model_id_or_slug: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> ManufacturingMetrics:
    wm = get_warehouse_model_by_identifier(db, model_id_or_slug, current_user.organization_id)
    if wm.slug.lower() not in ["manufacturing", "mfg"]:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Warehouse model '{wm.name}' is domain '{wm.domain}', not MANUFACTURING domain"
        )
    return get_manufacturing_analytics(db, current_user.organization_id)


# --- DEMO SEED & RESET ENDPOINTS ---
@router.post("/seed-sample-manufacturing", status_code=status.HTTP_201_CREATED)
def seed_sample_manufacturing_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    inserted = seed_sample_manufacturing(db, current_user.organization_id)
    return {
        "message": "Sample manufacturing star schema seeded successfully",
        "inserted_facts": inserted
    }


@router.post("/reset-manufacturing", status_code=status.HTTP_200_OK)
@router.delete("/reset-manufacturing", status_code=status.HTTP_200_OK)
def reset_manufacturing_data_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    deleted_info = clear_warehouse_manufacturing_data(db)
    return {
        "message": "Manufacturing star schema cleared successfully",
        "deleted": deleted_info
    }


# --- LEGACY / BACKWARD-COMPATIBLE ENDPOINTS ---
@router.get("/flat-datasets", response_model=List[WarehouseTableSummary])
def list_flat_transformed_datasets(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[WarehouseTableSummary]:
    return get_flat_transformed_datasets(db)


@router.get("/tables", response_model=List[WarehouseTableSummary])
def get_tables_summary(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> List[WarehouseTableSummary]:
    return get_warehouse_tables_summary(db)



@router.get("/tables/{table_name}", response_model=WarehouseTableDetail)
def get_table_detail(
    table_name: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> WarehouseTableDetail:
    try:
        return get_warehouse_table_detail(table_name, db)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )


@router.get("/analytics", response_model=RevenueMetrics)
def get_analytics_metrics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_read_access),
) -> RevenueMetrics:
    return get_warehouse_analytics(db)


@router.post("/seed-sample-sales", status_code=status.HTTP_201_CREATED)
def seed_sample_sales(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    sample_records = [
        {
            "order_id": "ORD-1001",
            "customer_id": "CUST-101",
            "customer_name": "Acme Global",
            "city": "New York",
            "product_id": "PROD-A",
            "product_name": "DataFusionX Enterprise License",
            "category": "Software",
            "quantity": 5,
            "unit_price": 5000.0,
            "discount": 500.0,
            "sale_date": "2026-08-01",
        },
        {
            "order_id": "ORD-1002",
            "customer_id": "CUST-102",
            "customer_name": "Apex Tech Solutions",
            "city": "San Francisco",
            "product_id": "PROD-B",
            "product_name": "Analytics Pro Module",
            "category": "Software",
            "quantity": 2,
            "unit_price": 2500.0,
            "discount": 0.0,
            "sale_date": "2026-08-03",
        },
        {
            "order_id": "ORD-1003",
            "customer_id": "CUST-101",
            "customer_name": "Acme Global",
            "city": "New York",
            "product_id": "PROD-C",
            "product_name": "24/7 Dedicated Support",
            "category": "Services",
            "quantity": 1,
            "unit_price": 10000.0,
            "discount": 1000.0,
            "sale_date": "2026-08-05",
        },
        {
            "order_id": "ORD-1004",
            "customer_id": "CUST-103",
            "customer_name": "Vortex Dynamics",
            "city": "London",
            "product_id": "PROD-A",
            "product_name": "DataFusionX Enterprise License",
            "category": "Software",
            "quantity": 10,
            "unit_price": 4500.0,
            "discount": 2000.0,
            "sale_date": "2026-08-07",
        },
    ]

    inserted = load_sales_star_schema(db, sample_records)
    return {"message": "Sample sales star schema seeded successfully", "inserted_facts": inserted}


@router.post("/reset", status_code=status.HTTP_200_OK)
@router.delete("/reset", status_code=status.HTTP_200_OK)
def reset_warehouse_data_endpoint(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_write_access),
):
    deleted_info = clear_warehouse_sales_data(db)
    return {
        "message": "Warehouse sales star schema cleared successfully",
        "deleted": deleted_info
    }
