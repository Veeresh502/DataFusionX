from datetime import datetime, date, timedelta, timezone
from typing import Dict, Any, List, Optional
import pandas as pd
from sqlalchemy import func, text, inspect
from sqlalchemy.orm import Session


from app.models.warehouse import (
    DimCustomer, DimProduct, DimDate, DimLocation, FactSales,
    DimMachine, DimPlant, FactProduction
)
from app.models.warehouse_model import WarehouseModel
from app.models.warehouse_table import WarehouseTable



def utcnow():
    return datetime.now(timezone.utc)


def populate_dim_date(db: Session, start_year: int = 2020, end_year: int = 2030):
    """Pre-populates dim_date table with calendar dates."""
    existing_count = db.query(DimDate).count()
    if existing_count > 0:
        return existing_count

    start_date = date(start_year, 1, 1)
    end_date = date(end_year, 12, 31)
    curr_date = start_date

    dates_to_insert = []
    while curr_date <= end_date:
        date_key = int(curr_date.strftime("%Y%m%d"))
        dates_to_insert.append(
            DimDate(
                date_key=date_key,
                full_date=curr_date,
                day=curr_date.day,
                month=curr_date.month,
                month_name=curr_date.strftime("%B"),
                quarter=(curr_date.month - 1) // 3 + 1,
                year=curr_date.year,
                day_of_week=curr_date.strftime("%A"),
            )
        )
        curr_date += timedelta(days=1)

    db.bulk_save_objects(dates_to_insert)
    db.commit()
    return len(dates_to_insert)


def upsert_dim_customer_scd2(
    db: Session,
    customer_id: str,
    customer_name: str,
    city: Optional[str] = None
) -> int:
    """
    Implements SCD Type 2 logic for dim_customer:
    If customer exists and attributes change, expires old row (is_current=False, end_date=now())
    and inserts new current row. Returns current surrogate customer_key.
    """
    now = utcnow()
    existing = db.query(DimCustomer).filter(
        DimCustomer.customer_id == str(customer_id),
        DimCustomer.is_current == True
    ).first()

    if not existing:
        new_cust = DimCustomer(
            customer_id=str(customer_id),
            customer_name=customer_name,
            city=city,
            effective_date=now,
            end_date=None,
            is_current=True,
        )
        db.add(new_cust)
        db.commit()
        db.refresh(new_cust)
        return new_cust.customer_key

    # Check for SCD Type 2 change
    if existing.customer_name != customer_name or existing.city != city:
        # Expire old record
        existing.is_current = False
        existing.end_date = now

        # Create new active record
        new_cust = DimCustomer(
            customer_id=str(customer_id),
            customer_name=customer_name,
            city=city,
            effective_date=now,
            end_date=None,
            is_current=True,
        )
        db.add(new_cust)
        db.commit()
        db.refresh(new_cust)
        return new_cust.customer_key

    return existing.customer_key


def upsert_dim_product(
    db: Session,
    product_id: str,
    product_name: str,
    category: str
) -> int:
    prod = db.query(DimProduct).filter(DimProduct.product_id == str(product_id)).first()
    if not prod:
        prod = DimProduct(
            product_id=str(product_id),
            product_name=product_name,
            category=category,
        )
        db.add(prod)
        db.commit()
        db.refresh(prod)
    elif prod.product_name != product_name or prod.category != category:
        prod.product_name = product_name
        prod.category = category
        db.commit()
    return prod.product_key


def upsert_dim_location(
    db: Session,
    city: str,
    region: Optional[str] = None,
    country: str = "USA"
) -> int:
    loc = db.query(DimLocation).filter(DimLocation.city == city).first()
    if not loc:
        loc = DimLocation(
            city=city,
            region=region,
            country=country,
        )
        db.add(loc)
        db.commit()
        db.refresh(loc)
    return loc.location_key


def get_date_key(sale_date: Optional[Any]) -> int:
    if isinstance(sale_date, (datetime, date)):
        return int(sale_date.strftime("%Y%m%d"))
    if isinstance(sale_date, str):
        try:
            parsed = datetime.strptime(sale_date[:10], "%Y-%m-%d")
            return int(parsed.strftime("%Y%m%d"))
        except Exception:
            pass
    return int(datetime.now(timezone.utc).strftime("%Y%m%d"))


def ensure_dim_date_key(db: Session, sale_date: Optional[Any]) -> int:

    """Gets date_key and ensures the date entry exists in dim_date without repopulating all years."""
    d_key = get_date_key(sale_date)
    existing = db.query(DimDate).filter(DimDate.date_key == d_key).first()
    if not existing:
        if isinstance(sale_date, (datetime, date)):
            dt = sale_date if isinstance(sale_date, date) else sale_date.date()
        elif isinstance(sale_date, str):
            try:
                dt = datetime.strptime(sale_date[:10], "%Y-%m-%d").date()
            except Exception:
                dt = date.today()
        else:
            dt = date.today()
            
        new_dim_date = DimDate(
            date_key=d_key,
            full_date=dt,
            day=dt.day,
            month=dt.month,
            month_name=dt.strftime("%B"),
            quarter=(dt.month - 1) // 3 + 1,
            year=dt.year,
            day_of_week=dt.strftime("%A"),
        )
        db.add(new_dim_date)
        db.commit()
    return d_key


def _extract_field_val(rec: dict, aliases: List[str], default: Any = None) -> Any:
    """Case-insensitive, alias-aware field extraction from dictionary records."""
    if not rec:
        return default

    # 1. Exact key match
    for k in aliases:
        if k in rec:
            val = rec[k]
            if pd.notnull(val) and val is not None and str(val).strip().lower() not in ["nan", "none", "null", ""]:
                return val

    # 2. Case-insensitive & stripped key match
    rec_clean = {str(k).strip().lower(): v for k, v in rec.items()}
    for k in aliases:
        k_clean = str(k).strip().lower()
        if k_clean in rec_clean:
            val = rec_clean[k_clean]
            if pd.notnull(val) and val is not None and str(val).strip().lower() not in ["nan", "none", "null", ""]:
                return val

    return default


def _parse_num(val: Any, default: Any, num_type: type = float) -> Any:
    """Parses numeric values, stripping currency symbols ($), commas, and percent signs."""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return default
    if str(val).strip().lower() in ["nan", "none", "null", ""]:
        return default
    try:
        cleaned = str(val).replace("$", "").replace(",", "").replace("%", "").strip()
        num = float(cleaned)
        if num_type is int:
            return int(round(num))
        return num
    except (ValueError, TypeError):
        return default


def load_dataframe_to_sales_warehouse(db: Session, df: pd.DataFrame) -> int:
    """
    Maps transformed ETL DataFrame records into Kimball Star Schema (dims + fact_sales).
    Implements SCD Type 2 for dim_customer, surrogate key resolution, date lookup,
    and duplicate fact protection at grain (order_id, product_key).
    """
    if df is None or df.empty:
        return 0

    populate_dim_date(db)

    # Convert DataFrame records to list of dicts for row-by-row mapping
    records = df.to_dict(orient="records")
    inserted_facts = 0

    for idx, rec in enumerate(records):
        # Extract string fields using alias candidates
        order_id_val = _extract_field_val(rec, ["order_id", "Order ID", "orderid", "order_num", "order_number", "id"])
        order_id = str(order_id_val).strip() if order_id_val is not None else f"ORD-{idx+1000}"

        cust_id_val = _extract_field_val(rec, ["customer_id", "Customer ID", "cust_id", "customer_num", "client_id"])
        cust_id = str(cust_id_val).strip() if cust_id_val is not None else f"CUST-{idx+1:03d}"

        cust_name_val = _extract_field_val(rec, ["customer_name", "Customer Name", "cust_name", "client_name", "customer"])
        cust_name = str(cust_name_val).strip() if cust_name_val is not None else f"Customer {cust_id}"

        city_val = _extract_field_val(rec, ["city", "City", "location", "Location", "town", "metro"])
        city = str(city_val).strip() if city_val is not None else "Unknown"

        prod_id_val = _extract_field_val(rec, ["product_id", "Product ID", "prod_id", "item_id", "sku"])
        prod_id = str(prod_id_val).strip() if prod_id_val is not None else f"PROD-{idx+1:03d}"

        prod_name_val = _extract_field_val(rec, ["product_name", "Product Name", "prod_name", "item_name", "product"])
        prod_name = str(prod_name_val).strip() if prod_name_val is not None else f"Product {prod_id}"

        category_val = _extract_field_val(rec, ["category", "Category", "product_category", "type"])
        category = str(category_val).strip() if category_val is not None else "General"

        region_val = _extract_field_val(rec, ["region", "Region", "state", "State", "zone"])
        region = str(region_val).strip() if region_val is not None else "East"

        country_val = _extract_field_val(rec, ["country", "Country", "nation"])
        country = str(country_val).strip() if country_val is not None else "USA"

        # Measures handling
        qty_raw = _extract_field_val(rec, ["quantity", "Quantity", "qty", "Qty", "units_sold", "units"])
        qty = _parse_num(qty_raw, default=1, num_type=int)

        unit_price_raw = _extract_field_val(rec, ["unit_price", "Unit Price", "unitprice", "price", "Price", "unit_cost"])
        unit_price = _parse_num(unit_price_raw, default=0.0, num_type=float)

        discount_raw = _extract_field_val(rec, ["discount", "Discount", "disc"])
        discount = _parse_num(discount_raw, default=0.0, num_type=float)

        revenue_raw = _extract_field_val(rec, ["revenue", "Revenue", "total_revenue", "Total_revenue", "total_amount", "sales_amount", "amount"])
        if revenue_raw is not None:
            revenue = _parse_num(revenue_raw, default=(qty * unit_price) - discount, num_type=float)
        else:
            revenue = float((qty * unit_price) - discount)

        sale_date_val = _extract_field_val(rec, ["order_date", "Order Date", "sale_date", "Sale Date", "date", "Date", "created_at"])

        # 1. Resolve Surrogate Keys
        c_key = upsert_dim_customer_scd2(db, cust_id, cust_name, city)
        p_key = upsert_dim_product(db, prod_id, prod_name, category)
        l_key = upsert_dim_location(db, city, region, country)
        d_key = ensure_dim_date_key(db, sale_date_val)

        # 2. Duplicate Fact Protection at grain (order_id, product_key)
        existing_fact = db.query(FactSales).filter(
            FactSales.order_id == order_id,
            FactSales.product_key == p_key
        ).first()

        if existing_fact:
            continue

        # 3. Create & Insert Fact Row
        fact = FactSales(
            order_id=order_id,
            customer_key=c_key,
            product_key=p_key,
            date_key=d_key,
            location_key=l_key,
            quantity=qty,
            unit_price=unit_price,
            discount=discount,
            revenue=revenue,
        )
        db.add(fact)
        inserted_facts += 1

    db.commit()
    return inserted_facts



def load_sales_star_schema(db: Session, records: List[Dict[str, Any]]) -> int:
    """Loads sales transaction records into Kimball Star Schema (dims + fact_sales)."""
    df = pd.DataFrame(records) if records else pd.DataFrame()
    return load_dataframe_to_sales_warehouse(db, df)


def clear_warehouse_sales_data(db: Session) -> Dict[str, int]:
    """Clears/resets all sales star schema tables for safe testing/development."""
    deleted_facts = db.query(FactSales).delete()
    deleted_cust = db.query(DimCustomer).delete()
    deleted_prod = db.query(DimProduct).delete()
    deleted_loc = db.query(DimLocation).delete()
    db.commit()
    return {
        "fact_sales": deleted_facts,
        "dim_customer": deleted_cust,
        "dim_product": deleted_prod,
        "dim_location": deleted_loc,
    }



def get_warehouse_analytics(db: Session) -> Dict[str, Any]:
    """Computes analytical metrics from the Sales Star Schema."""
    total_rev = db.query(func.coalesce(func.sum(FactSales.revenue), 0.0)).scalar()
    total_qty = db.query(func.coalesce(func.sum(FactSales.quantity), 0)).scalar()
    distinct_orders = db.query(func.count(func.distinct(FactSales.order_id))).scalar()
    aov = round(total_rev / distinct_orders, 2) if distinct_orders > 0 else 0.0

    # Revenue by Product
    rev_prod = (
        db.query(
            DimProduct.product_name,
            func.sum(FactSales.revenue).label("revenue"),
            func.sum(FactSales.quantity).label("quantity")
        )
        .join(FactSales, FactSales.product_key == DimProduct.product_key)
        .group_by(DimProduct.product_name)
        .order_by(text("revenue DESC"))
        .all()
    )
    revenue_by_product = [{"product_name": r[0], "revenue": round(r[1], 2), "quantity": r[2]} for r in rev_prod]

    # Revenue by Category
    rev_cat = (
        db.query(
            DimProduct.category,
            func.sum(FactSales.revenue).label("revenue")
        )
        .join(FactSales, FactSales.product_key == DimProduct.product_key)
        .group_by(DimProduct.category)
        .order_by(text("revenue DESC"))
        .all()
    )
    revenue_by_category = [{"category": r[0], "revenue": round(r[1], 2)} for r in rev_cat]

    # Revenue by Customer
    rev_cust = (
        db.query(
            DimCustomer.customer_name,
            func.sum(FactSales.revenue).label("revenue")
        )
        .join(FactSales, FactSales.customer_key == DimCustomer.customer_key)
        .group_by(DimCustomer.customer_name)
        .order_by(text("revenue DESC"))
        .all()
    )
    revenue_by_customer = [{"customer_name": r[0], "revenue": round(r[1], 2)} for r in rev_cust]

    # Revenue by City
    rev_city = (
        db.query(
            DimLocation.city,
            func.sum(FactSales.revenue).label("revenue")
        )
        .join(FactSales, FactSales.location_key == DimLocation.location_key)
        .group_by(DimLocation.city)
        .order_by(text("revenue DESC"))
        .all()
    )
    revenue_by_city = [{"city": r[0], "revenue": round(r[1], 2)} for r in rev_city]

    # Revenue by Month
    rev_month = (
        db.query(
            DimDate.year,
            DimDate.month_name,
            func.sum(FactSales.revenue).label("revenue")
        )
        .join(FactSales, FactSales.date_key == DimDate.date_key)
        .group_by(DimDate.year, DimDate.month, DimDate.month_name)
        .order_by(DimDate.year, DimDate.month)
        .all()
    )
    revenue_by_month = [{"month": f"{r[1]} {r[0]}", "revenue": round(r[2], 2)} for r in rev_month]

    return {
        "total_revenue": round(total_rev, 2),
        "total_quantity": total_qty,
        "average_order_value": aov,
        "revenue_by_product": revenue_by_product,
        "revenue_by_category": revenue_by_category,
        "revenue_by_customer": revenue_by_customer,
        "revenue_by_city": revenue_by_city,
        "revenue_by_month": revenue_by_month,
        "top_products": revenue_by_product[:5],
    }


# --- GENERIC WAREHOUSE MODEL INITIALIZATION & SEEDING ---
def ensure_default_warehouse_models(db: Session, organization_id: int):
    """Ensures default Sales Analytics and Manufacturing Analytics models exist for an organization."""
    # 1. Sales Model
    sales_model = db.query(WarehouseModel).filter(
        WarehouseModel.organization_id == organization_id,
        WarehouseModel.slug == "sales"
    ).first()

    if not sales_model:
        sales_model = WarehouseModel(
            organization_id=organization_id,
            name="Sales Analytics",
            slug="sales",
            domain="SALES",
            description="Kimball Star Schema for Sales Orders, Customers, Products, and Revenue Analytics",
            is_active=True,
        )
        db.add(sales_model)
        db.commit()
        db.refresh(sales_model)

        sales_tables = [
            WarehouseTable(
                warehouse_model_id=sales_model.id,
                table_name="fact_sales",
                table_type="FACT",
                description="Line-item sales order facts",
                grain="One row per customer order line item",
                primary_keys=["sale_key"],
                foreign_keys=["customer_key", "product_key", "date_key", "location_key"],
            ),
            WarehouseTable(
                warehouse_model_id=sales_model.id,
                table_name="dim_customer",
                table_type="DIMENSION",
                description="Customer dimension with SCD Type 2 history",
                grain="One row per customer version",
                primary_keys=["customer_key"],
                foreign_keys=[],
            ),
            WarehouseTable(
                warehouse_model_id=sales_model.id,
                table_name="dim_product",
                table_type="DIMENSION",
                description="Product catalog dimension",
                grain="One row per product SKU",
                primary_keys=["product_key"],
                foreign_keys=[],
            ),
            WarehouseTable(
                warehouse_model_id=sales_model.id,
                table_name="dim_location",
                table_type="DIMENSION",
                description="Geographic location dimension",
                grain="One row per city",
                primary_keys=["location_key"],
                foreign_keys=[],
            ),
            WarehouseTable(
                warehouse_model_id=sales_model.id,
                table_name="dim_date",
                table_type="DIMENSION",
                description="Shared calendar date dimension",
                grain="One row per calendar date",
                primary_keys=["date_key"],
                foreign_keys=[],
            ),
        ]
        db.add_all(sales_tables)

    # 2. Manufacturing Model
    mfg_model = db.query(WarehouseModel).filter(
        WarehouseModel.organization_id == organization_id,
        WarehouseModel.slug == "manufacturing"
    ).first()

    if not mfg_model:
        mfg_model = WarehouseModel(
            organization_id=organization_id,
            name="Manufacturing Analytics",
            slug="manufacturing",
            domain="MANUFACTURING",
            description="Manufacturing Star Schema for Production Batches, Machines, Plants, Defects, and Operating Hours",
            is_active=True,
        )
        db.add(mfg_model)
        db.commit()
        db.refresh(mfg_model)

        mfg_tables = [
            WarehouseTable(
                warehouse_model_id=mfg_model.id,
                table_name="fact_production",
                table_type="FACT",
                description="Production run fact table",
                grain="One row per machine production run batch",
                primary_keys=["production_key"],
                foreign_keys=["date_key", "machine_key", "plant_key"],
            ),
            WarehouseTable(
                warehouse_model_id=mfg_model.id,
                table_name="dim_machine",
                table_type="DIMENSION",
                description="Plant machine asset dimension",
                grain="One row per machine",
                primary_keys=["machine_key"],
                foreign_keys=[],
            ),
            WarehouseTable(
                warehouse_model_id=mfg_model.id,
                table_name="dim_plant",
                table_type="DIMENSION",
                description="Manufacturing plant facility dimension",
                grain="One row per plant facility",
                primary_keys=["plant_key"],
                foreign_keys=[],
            ),
            WarehouseTable(
                warehouse_model_id=mfg_model.id,
                table_name="dim_date",
                table_type="DIMENSION",
                description="Shared calendar date dimension",
                grain="One row per calendar date",
                primary_keys=["date_key"],
                foreign_keys=[],
            ),
        ]
        db.add_all(mfg_tables)

    db.commit()


# --- GENERIC WAREHOUSE LOADER ENGINE ---
def load_dataframe_to_warehouse(
    db: Session,
    df: pd.DataFrame,
    warehouse_model_identifier: Optional[Any] = None,
    dest_config: Optional[Dict[str, Any]] = None
) -> int:
    """
    Generic Warehouse Loading Interface:
    Determines the warehouse model domain (e.g. Sales, Manufacturing) and dispatches
    the transformed DataFrame to the domain-specific loader.
    """
    if df is None or df.empty:
        return 0

    dest_config = dest_config or {}
    model_id_val = warehouse_model_identifier or dest_config.get("warehouse_model_id") or dest_config.get("warehouse_model_slug") or dest_config.get("warehouse_model") or "sales"

    target_slug = "sales"
    if isinstance(model_id_val, int) or (isinstance(model_id_val, str) and model_id_val.isdigit()):
        wm = db.query(WarehouseModel).filter(WarehouseModel.id == int(model_id_val)).first()
        if wm:
            target_slug = wm.slug.lower()
    elif isinstance(model_id_val, str):
        target_slug = model_id_val.lower()

    if target_slug in ["manufacturing", "mfg"]:
        return load_dataframe_to_manufacturing_warehouse(db, df)
    else:
        return load_dataframe_to_sales_warehouse(db, df)


# --- MANUFACTURING DOMAIN LOADER ---
def upsert_dim_machine(db: Session, machine_id: str, machine_name: str) -> int:
    mach = db.query(DimMachine).filter(DimMachine.machine_id == str(machine_id)).first()
    if not mach:
        mach = DimMachine(
            machine_id=str(machine_id),
            machine_name=machine_name,
        )
        db.add(mach)
        db.commit()
        db.refresh(mach)
    elif mach.machine_name != machine_name:
        mach.machine_name = machine_name
        db.commit()
    return mach.machine_key


def upsert_dim_plant(db: Session, plant_id: str, plant_name: str) -> int:
    plant = db.query(DimPlant).filter(DimPlant.plant_id == str(plant_id)).first()
    if not plant:
        plant = DimPlant(
            plant_id=str(plant_id),
            plant_name=plant_name,
        )
        db.add(plant)
        db.commit()
        db.refresh(plant)
    elif plant.plant_name != plant_name:
        plant.plant_name = plant_name
        db.commit()
    return plant.plant_key


def load_dataframe_to_manufacturing_warehouse(db: Session, df: pd.DataFrame) -> int:
    """
    Loads manufacturing production run records into Manufacturing Star Schema
    (dim_machine, dim_plant, dim_date, fact_production).
    """
    if df is None or df.empty:
        return 0

    populate_dim_date(db)
    records = df.to_dict(orient="records")
    inserted_facts = 0

    for idx, rec in enumerate(records):
        prod_id_val = _extract_field_val(rec, ["production_id", "Production ID", "prod_id", "batch_id"])
        prod_id = str(prod_id_val).strip() if prod_id_val is not None else f"PROD-RUN-{idx+1000}"
        
        mach_id_val = _extract_field_val(rec, ["machine_id", "Machine ID", "mach_id"])
        mach_id = str(mach_id_val).strip() if mach_id_val is not None else "M001"

        mach_name_val = _extract_field_val(rec, ["machine_name", "Machine Name", "mach_name"])
        mach_name = str(mach_name_val).strip() if mach_name_val is not None else f"Machine {mach_id}"

        plant_id_val = _extract_field_val(rec, ["plant_id", "Plant ID"])
        plant_id = str(plant_id_val).strip() if plant_id_val is not None else "PL01"

        plant_name_val = _extract_field_val(rec, ["plant_name", "Plant Name"])
        plant_name = str(plant_name_val).strip() if plant_name_val is not None else f"Plant {plant_id}"

        units_raw = _extract_field_val(rec, ["units_produced", "Units Produced", "units", "quantity"])
        units = _parse_num(units_raw, default=0, num_type=int)

        defects_raw = _extract_field_val(rec, ["defect_count", "Defect Count", "defects"])
        defects = _parse_num(defects_raw, default=0, num_type=int)

        hours_raw = _extract_field_val(rec, ["operating_hours", "Operating Hours", "hours"])
        hours = _parse_num(hours_raw, default=0.0, num_type=float)

        prod_date_val = _extract_field_val(rec, ["production_date", "Production Date", "date", "Date"])


        # 1. Resolve Surrogate Keys
        m_key = upsert_dim_machine(db, mach_id, mach_name)
        p_key = upsert_dim_plant(db, plant_id, plant_name)
        d_key = ensure_dim_date_key(db, prod_date_val)

        # 2. Duplicate Fact Protection at grain (production_id, machine_key)
        existing_fact = db.query(FactProduction).filter(
            FactProduction.production_id == prod_id,
            FactProduction.machine_key == m_key
        ).first()

        if existing_fact:
            continue

        # 3. Create Fact Record
        fact = FactProduction(
            production_id=prod_id,
            date_key=d_key,
            machine_key=m_key,
            plant_key=p_key,
            units_produced=units,
            defect_count=defects,
            operating_hours=hours,
        )
        db.add(fact)
        inserted_facts += 1

    db.commit()
    return inserted_facts


def seed_sample_manufacturing(db: Session, organization_id: int) -> int:
    """Seeds sample manufacturing records for demo/testing."""
    sample_records = [
        {
            "production_id": "P001",
            "production_date": "2026-08-01",
            "machine_id": "M001",
            "machine_name": "CNC Lathe Alpha",
            "plant_id": "PL01",
            "plant_name": "Austin Assembly Plant",
            "units_produced": 1000,
            "defect_count": 20,
            "operating_hours": 8.0,
        },
        {
            "production_id": "P002",
            "production_date": "2026-08-01",
            "machine_id": "M002",
            "machine_name": "Stamping Press Beta",
            "plant_id": "PL01",
            "plant_name": "Austin Assembly Plant",
            "units_produced": 850,
            "defect_count": 15,
            "operating_hours": 8.0,
        },
        {
            "production_id": "P003",
            "production_date": "2026-08-02",
            "machine_id": "M001",
            "machine_name": "CNC Lathe Alpha",
            "plant_id": "PL02",
            "plant_name": "Seattle Tech Works",
            "units_produced": 1100,
            "defect_count": 18,
            "operating_hours": 8.0,
        },
        {
            "production_id": "P004",
            "production_date": "2026-08-03",
            "machine_id": "M003",
            "machine_name": "Robotic Welder Gamma",
            "plant_id": "PL02",
            "plant_name": "Seattle Tech Works",
            "units_produced": 1500,
            "defect_count": 45,
            "operating_hours": 12.0,
        },
    ]

    df = pd.DataFrame(sample_records)
    return load_dataframe_to_manufacturing_warehouse(db, df)


def clear_warehouse_manufacturing_data(db: Session) -> Dict[str, int]:
    """Clears/resets all manufacturing star schema tables."""
    del_fact = db.query(FactProduction).delete()
    del_mach = db.query(DimMachine).delete()
    del_plant = db.query(DimPlant).delete()
    db.commit()
    return {
        "fact_production": del_fact,
        "dim_machine": del_mach,
        "dim_plant": del_plant,
    }


# --- MODEL-AWARE WAREHOUSE APIS & METRICS SERVICES ---
def get_warehouse_models_list(db: Session, organization_id: int) -> List[WarehouseModel]:
    ensure_default_warehouse_models(db, organization_id)
    models = db.query(WarehouseModel).filter(
        WarehouseModel.organization_id == organization_id,
        WarehouseModel.is_active == True
    ).order_by(WarehouseModel.id.asc()).all()

    seen_slugs = set()
    unique_models = []
    for m in models:
        if m.slug.lower() not in seen_slugs:
            seen_slugs.add(m.slug.lower())
            unique_models.append(m)
    return unique_models



def get_warehouse_model_by_identifier(db: Session, model_id_or_slug: Any, organization_id: int) -> WarehouseModel:
    ensure_default_warehouse_models(db, organization_id)
    query = db.query(WarehouseModel).filter(WarehouseModel.organization_id == organization_id)
    
    if isinstance(model_id_or_slug, int) or (isinstance(model_id_or_slug, str) and model_id_or_slug.isdigit()):
        wm = query.filter(WarehouseModel.id == int(model_id_or_slug)).first()
    else:
        wm = query.filter(func.lower(WarehouseModel.slug) == str(model_id_or_slug).lower()).first()

    if not wm:
        raise ValueError(f"Warehouse model '{model_id_or_slug}' not found for organization")

    return wm



def get_generic_model_analytics(db: Session, model: WarehouseModel) -> Dict[str, Any]:
    """Computes generic model-independent metrics for any registered warehouse model."""
    table_summaries = []
    total_fact_rows = 0
    total_dim_rows = 0
    fact_count = 0
    dim_count = 0

    model_map = {
        "fact_sales": (FactSales, ["sale_key"], ["customer_key", "product_key", "date_key", "location_key"]),
        "dim_customer": (DimCustomer, ["customer_key"], []),
        "dim_product": (DimProduct, ["product_key"], []),
        "dim_date": (DimDate, ["date_key"], []),
        "dim_location": (DimLocation, ["location_key"], []),
        "fact_production": (FactProduction, ["production_key"], ["date_key", "machine_key", "plant_key"]),
        "dim_machine": (DimMachine, ["machine_key"], []),
        "dim_plant": (DimPlant, ["plant_key"], []),
    }

    for t in model.tables:
        t_name = t.table_name
        if t_name in model_map:
            m_cls, pks, fks = model_map[t_name]
            r_cnt = db.query(m_cls).count()
            c_cnt = len(m_cls.__table__.columns)
        else:
            r_cnt = 0
            c_cnt = 0
            pks = t.primary_keys or []
            fks = t.foreign_keys or []

        table_summaries.append({
            "table_name": t_name,
            "column_count": c_cnt,
            "row_count": r_cnt,
            "primary_keys": pks,
            "foreign_keys": fks,
        })

        if t.table_type == "FACT":
            fact_count += 1
            total_fact_rows += r_cnt
        else:
            dim_count += 1
            total_dim_rows += r_cnt

    return {
        "model_id": model.id,
        "model_name": model.name,
        "domain": model.domain,
        "total_fact_rows": total_fact_rows,
        "total_dimension_rows": total_dim_rows,
        "fact_table_count": fact_count,
        "dimension_table_count": dim_count,
        "tables_summary": table_summaries,
        "last_updated": datetime.now(timezone.utc).isoformat(),
    }


def get_manufacturing_analytics(db: Session, organization_id: int) -> Dict[str, Any]:
    """Computes Manufacturing-specific analytical metrics."""
    tot_batches = db.query(FactProduction).count()
    tot_units = db.query(func.coalesce(func.sum(FactProduction.units_produced), 0)).scalar()
    tot_defects = db.query(func.coalesce(func.sum(FactProduction.defect_count), 0)).scalar()
    tot_hours = db.query(func.coalesce(func.sum(FactProduction.operating_hours), 0.0)).scalar()

    defect_rate = round((tot_defects / tot_units * 100.0), 2) if tot_units > 0 else 0.0

    prod_mach = (
        db.query(
            DimMachine.machine_name,
            func.sum(FactProduction.units_produced).label("units"),
            func.sum(FactProduction.defect_count).label("defects")
        )
        .join(FactProduction, FactProduction.machine_key == DimMachine.machine_key)
        .group_by(DimMachine.machine_name)
        .all()
    )
    production_by_machine = [
        {"machine_name": r[0], "units_produced": r[1], "defect_count": r[2]} for r in prod_mach
    ]

    def_plant = (
        db.query(
            DimPlant.plant_name,
            func.sum(FactProduction.defect_count).label("defects"),
            func.sum(FactProduction.units_produced).label("units")
        )
        .join(FactProduction, FactProduction.plant_key == DimPlant.plant_key)
        .group_by(DimPlant.plant_name)
        .all()
    )
    defects_by_plant = [
        {"plant_name": r[0], "defect_count": r[1], "units_produced": r[2]} for r in def_plant
    ]

    return {
        "total_production_batches": tot_batches,
        "total_units_produced": tot_units,
        "total_defect_count": tot_defects,
        "defect_rate_percentage": defect_rate,
        "total_operating_hours": round(tot_hours, 1),
        "production_by_machine": production_by_machine,
        "defects_by_plant": defects_by_plant,
    }


def get_warehouse_tables_summary(db: Session, model_slug_or_id: Optional[Any] = None) -> List[Dict[str, Any]]:
    """Returns summary of star schema tables for a given model or default all."""
    tables_map = [
        {"table_name": "fact_sales", "model": FactSales, "pks": ["sale_key"], "fks": ["customer_key", "product_key", "date_key", "location_key"]},
        {"table_name": "dim_customer", "model": DimCustomer, "pks": ["customer_key"], "fks": []},
        {"table_name": "dim_product", "model": DimProduct, "pks": ["product_key"], "fks": []},
        {"table_name": "dim_date", "model": DimDate, "pks": ["date_key"], "fks": []},
        {"table_name": "dim_location", "model": DimLocation, "pks": ["location_key"], "fks": []},
        {"table_name": "fact_production", "model": FactProduction, "pks": ["production_key"], "fks": ["date_key", "machine_key", "plant_key"]},
        {"table_name": "dim_machine", "model": DimMachine, "pks": ["machine_key"], "fks": []},
        {"table_name": "dim_plant", "model": DimPlant, "pks": ["plant_key"], "fks": []},
    ]

    if model_slug_or_id:
        slug_str = str(model_slug_or_id).lower()
        if slug_str in ["sales", "sales_analytics"]:
            allowed = ["fact_sales", "dim_customer", "dim_product", "dim_location", "dim_date"]
        elif slug_str in ["manufacturing", "mfg"]:
            allowed = ["fact_production", "dim_machine", "dim_plant", "dim_date"]
        else:
            allowed = [t["table_name"] for t in tables_map]
    else:
        allowed = [t["table_name"] for t in tables_map]

    result = []
    for t in tables_map:
        if t["table_name"] in allowed:
            cnt = db.query(t["model"]).count()
            col_cnt = len(t["model"].__table__.columns)
            result.append({
                "table_name": t["table_name"],
                "column_count": col_cnt,
                "row_count": cnt,
                "primary_keys": t["pks"],
                "foreign_keys": t["fks"],
            })

    return result


def get_flat_transformed_datasets(db: Session) -> List[Dict[str, Any]]:
    """Returns a list of all generic flat transformed PostgreSQL tables loaded by ETL pipelines."""
    inspector = inspect(db.bind)
    all_tables = inspector.get_table_names()

    system_and_star_tables = {
        "alembic_version", "organizations", "users", "projects", "data_sources",
        "pipelines", "pipeline_executions", "pipeline_schedules", "data_profiles",
        "warehouse_models", "warehouse_tables",
        "fact_sales", "dim_customer", "dim_product", "dim_location", "dim_date",
        "fact_production", "dim_machine", "dim_plant"
    }

    flat_tables = [t for t in all_tables if t not in system_and_star_tables]

    result = []
    for t_name in flat_tables:
        try:
            col_info = inspector.get_columns(t_name)
            col_count = len(col_info)
            row_count_res = db.execute(text(f'SELECT COUNT(*) FROM "{t_name}"')).scalar()
            row_count = int(row_count_res or 0)

            pk_info = inspector.get_pk_constraint(t_name)
            pks = pk_info.get("constrained_columns", []) if pk_info else []

            result.append({
                "table_name": t_name,
                "column_count": col_count,
                "row_count": row_count,
                "primary_keys": pks,
                "foreign_keys": [],
            })
        except Exception:
            continue

    return result


def get_warehouse_table_detail(table_name: str, db: Session) -> Dict[str, Any]:
    """Returns detailed columns, types, PKs/FKs, and sample records for any warehouse or flat table."""
    model_map = {
        "fact_sales": (FactSales, ["sale_key"], ["customer_key", "product_key", "date_key", "location_key"]),
        "dim_customer": (DimCustomer, ["customer_key"], []),
        "dim_product": (DimProduct, ["product_key"], []),
        "dim_date": (DimDate, ["date_key"], []),
        "dim_location": (DimLocation, ["location_key"], []),
        "fact_production": (FactProduction, ["production_key"], ["date_key", "machine_key", "plant_key"]),
        "dim_machine": (DimMachine, ["machine_key"], []),
        "dim_plant": (DimPlant, ["plant_key"], []),
    }

    if table_name in model_map:
        model, pks, fks = model_map[table_name]
        row_count = db.query(model).count()
        sample_objs = db.query(model).limit(20).all()

        columns_info = []
        for col in model.__table__.columns:
            columns_info.append({
                "name": col.name,
                "type": str(col.type),
                "is_primary_key": col.primary_key,
                "is_foreign_key": col.name in fks,
            })

        sample_records = []
        for obj in sample_objs:
            row_dict = {}
            for col in model.__table__.columns:
                val = getattr(obj, col.name)
                if isinstance(val, (datetime, date)):
                    val = str(val)
                row_dict[col.name] = val
            sample_records.append(row_dict)

        return {
            "table_name": table_name,
            "columns": columns_info,
            "primary_keys": pks,
            "foreign_keys": fks,
            "row_count": row_count,
            "sample_records": sample_records,
        }

    # Inspection for generic flat PostgreSQL tables
    inspector = inspect(db.bind)
    if table_name not in inspector.get_table_names():
        raise ValueError(f"Table '{table_name}' does not exist in database")

    col_info = inspector.get_columns(table_name)
    row_count_res = db.execute(text(f'SELECT COUNT(*) FROM "{table_name}"')).scalar()
    row_count = int(row_count_res or 0)

    pk_info = inspector.get_pk_constraint(table_name)
    pks = pk_info.get("constrained_columns", []) if pk_info else []

    columns_info = []
    for c in col_info:
        columns_info.append({
            "name": c["name"],
            "type": str(c["type"]),
            "is_primary_key": c["name"] in pks,
            "is_foreign_key": False,
        })

    raw_sample = db.execute(text(f'SELECT * FROM "{table_name}" LIMIT 20')).mappings().all()
    sample_records = [dict(row) for row in raw_sample]

    return {
        "table_name": table_name,
        "columns": columns_info,
        "primary_keys": pks,
        "foreign_keys": [],
        "row_count": row_count,
        "sample_records": sample_records,
    }


