from datetime import datetime, date, timezone
from sqlalchemy import Column, Integer, String, Float, Boolean, Date, DateTime, ForeignKey, func
from sqlalchemy.orm import relationship
from app.db.base import Base


def utcnow():
    return datetime.now(timezone.utc)


class DimCustomer(Base):
    __tablename__ = "dim_customer"

    customer_key = Column(Integer, primary_key=True, index=True, autoincrement=True)  # Surrogate Key
    customer_id = Column(String, nullable=False, index=True)                          # Business Key
    customer_name = Column(String, nullable=False)
    city = Column(String, nullable=True)
    
    # SCD Type 2 Tracking Fields
    effective_date = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    end_date = Column(DateTime(timezone=True), nullable=True)
    is_current = Column(Boolean, default=True, nullable=False, index=True)

    sales = relationship("FactSales", back_populates="customer")


class DimProduct(Base):
    __tablename__ = "dim_product"

    product_key = Column(Integer, primary_key=True, index=True, autoincrement=True)   # Surrogate Key
    product_id = Column(String, nullable=False, index=True)                           # Business Key
    product_name = Column(String, nullable=False)
    category = Column(String, nullable=False)

    sales = relationship("FactSales", back_populates="product")


class DimDate(Base):
    __tablename__ = "dim_date"

    date_key = Column(Integer, primary_key=True, index=True)  # YYYYMMDD e.g. 20260808
    full_date = Column(Date, unique=True, nullable=False, index=True)
    day = Column(Integer, nullable=False)
    month = Column(Integer, nullable=False)
    month_name = Column(String, nullable=False)
    quarter = Column(Integer, nullable=False)
    year = Column(Integer, nullable=False)
    day_of_week = Column(String, nullable=False)

    sales = relationship("FactSales", back_populates="date")


class DimLocation(Base):
    __tablename__ = "dim_location"

    location_key = Column(Integer, primary_key=True, index=True, autoincrement=True)  # Surrogate Key
    city = Column(String, nullable=False, index=True)
    region = Column(String, nullable=True)
    country = Column(String, nullable=False, default="USA")

    sales = relationship("FactSales", back_populates="location")


class FactSales(Base):
    __tablename__ = "fact_sales"

    sale_key = Column(Integer, primary_key=True, index=True, autoincrement=True)
    order_id = Column(String, nullable=False, index=True)
    
    # Foreign Keys referencing Surrogate Keys of Dimensions
    customer_key = Column(Integer, ForeignKey("dim_customer.customer_key"), nullable=False, index=True)
    product_key = Column(Integer, ForeignKey("dim_product.product_key"), nullable=False, index=True)
    date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, index=True)
    location_key = Column(Integer, ForeignKey("dim_location.location_key"), nullable=False, index=True)

    # Measures / Facts
    quantity = Column(Integer, nullable=False, default=1)
    unit_price = Column(Float, nullable=False, default=0.0)
    discount = Column(Float, nullable=False, default=0.0)
    revenue = Column(Float, nullable=False, default=0.0)

    customer = relationship("DimCustomer", back_populates="sales")
    product = relationship("DimProduct", back_populates="sales")
    date = relationship("DimDate", back_populates="sales")
    location = relationship("DimLocation", back_populates="sales")


# --- MANUFACTURING PROOF-OF-CONCEPT MODELS ---
class DimMachine(Base):
    __tablename__ = "dim_machine"

    machine_key = Column(Integer, primary_key=True, index=True, autoincrement=True)  # Surrogate Key
    machine_id = Column(String, nullable=False, index=True)                          # Business Key
    machine_name = Column(String, nullable=False)

    productions = relationship("FactProduction", back_populates="machine")


class DimPlant(Base):
    __tablename__ = "dim_plant"

    plant_key = Column(Integer, primary_key=True, index=True, autoincrement=True)    # Surrogate Key
    plant_id = Column(String, nullable=False, index=True)                            # Business Key
    plant_name = Column(String, nullable=False)

    productions = relationship("FactProduction", back_populates="plant")


class FactProduction(Base):
    __tablename__ = "fact_production"

    production_key = Column(Integer, primary_key=True, index=True, autoincrement=True)
    production_id = Column(String, nullable=False, index=True)

    date_key = Column(Integer, ForeignKey("dim_date.date_key"), nullable=False, index=True)
    machine_key = Column(Integer, ForeignKey("dim_machine.machine_key"), nullable=False, index=True)
    plant_key = Column(Integer, ForeignKey("dim_plant.plant_key"), nullable=False, index=True)

    units_produced = Column(Integer, nullable=False, default=0)
    defect_count = Column(Integer, nullable=False, default=0)
    operating_hours = Column(Float, nullable=False, default=0.0)

    date = relationship("DimDate")
    machine = relationship("DimMachine", back_populates="productions")
    plant = relationship("DimPlant", back_populates="productions")

