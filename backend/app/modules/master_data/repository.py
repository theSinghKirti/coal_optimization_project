import uuid

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.modules.master_data.models import CoalCompany, Plant, PlantAlias, Supplier


# ---- Plant ----
def create_plant(db: Session, **kwargs) -> Plant:
    plant = Plant(**kwargs)
    db.add(plant)
    db.flush()
    return plant


def get_plant(db: Session, plant_id: uuid.UUID) -> Plant | None:
    return db.get(Plant, plant_id)


def get_plant_by_code(db: Session, plant_code: str) -> Plant | None:
    return db.execute(select(Plant).where(Plant.plant_code == plant_code)).scalar_one_or_none()


def list_plants(db: Session, *, is_active: bool | None = None, limit: int = 50, offset: int = 0):
    stmt = select(Plant)
    count_stmt = select(func.count()).select_from(Plant)
    if is_active is not None:
        stmt = stmt.where(Plant.is_active == is_active)
        count_stmt = count_stmt.where(Plant.is_active == is_active)
    total = db.execute(count_stmt).scalar_one()
    stmt = stmt.order_by(Plant.plant_code).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


# ---- Plant Alias ----
def create_alias(db: Session, **kwargs) -> PlantAlias:
    alias = PlantAlias(**kwargs)
    db.add(alias)
    db.flush()
    return alias


def get_alias_by_name(db: Session, alias_name: str) -> PlantAlias | None:
    return db.execute(select(PlantAlias).where(PlantAlias.alias_name == alias_name)).scalar_one_or_none()


def list_aliases(db: Session, *, plant_id: uuid.UUID | None = None) -> list[PlantAlias]:
    stmt = select(PlantAlias)
    if plant_id:
        stmt = stmt.where(PlantAlias.plant_id == plant_id)
    return list(db.execute(stmt).scalars().all())


# ---- Coal Company ----
def create_coal_company(db: Session, **kwargs) -> CoalCompany:
    company = CoalCompany(**kwargs)
    db.add(company)
    db.flush()
    return company


def list_coal_companies(db: Session, *, limit: int = 50, offset: int = 0):
    total = db.execute(select(func.count()).select_from(CoalCompany)).scalar_one()
    stmt = select(CoalCompany).order_by(CoalCompany.name).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def get_coal_company(db: Session, company_id: uuid.UUID) -> CoalCompany | None:
    return db.get(CoalCompany, company_id)


# ---- Supplier ----
def create_supplier(db: Session, **kwargs) -> Supplier:
    supplier = Supplier(**kwargs)
    db.add(supplier)
    db.flush()
    return supplier


def list_suppliers(db: Session, *, limit: int = 50, offset: int = 0):
    total = db.execute(select(func.count()).select_from(Supplier)).scalar_one()
    stmt = select(Supplier).order_by(Supplier.name).offset(offset).limit(limit)
    return list(db.execute(stmt).scalars().all()), total


def get_supplier(db: Session, supplier_id: uuid.UUID) -> Supplier | None:
    return db.get(Supplier, supplier_id)
