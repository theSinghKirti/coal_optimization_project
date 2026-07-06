import uuid

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.pagination import Page, PageParams
from app.core.database import get_db
from app.modules.master_data import service
from app.modules.master_data.schemas import (
    CoalCompanyCreate,
    CoalCompanyRead,
    PlantAliasCreate,
    PlantAliasRead,
    PlantCreate,
    PlantRead,
    PlantUpdate,
    SupplierCreate,
    SupplierRead,
)

router = APIRouter(tags=["Master Data"])


# ---- Plants ----
@router.post("/plants", response_model=PlantRead, status_code=status.HTTP_201_CREATED)
def create_plant(payload: PlantCreate, db: Session = Depends(get_db)):
    plant = service.create_plant(db, payload)
    db.commit()
    return plant


@router.get("/plants", response_model=Page[PlantRead])
def list_plants(
    is_active: bool | None = Query(default=None),
    page_params: PageParams = Depends(),
    db: Session = Depends(get_db),
):
    items, total = service.list_plants(
        db, is_active=is_active, limit=page_params.page_size, offset=page_params.offset
    )
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


# ---- Plant Aliases (registered before /plants/{plant_id} so the static
#      "aliases" path segment is never swallowed by the dynamic route) ----
@router.post("/plants/aliases", response_model=PlantAliasRead, status_code=status.HTTP_201_CREATED)
def create_alias(payload: PlantAliasCreate, db: Session = Depends(get_db)):
    alias = service.create_alias(db, payload)
    db.commit()
    return alias


@router.get("/plants/aliases", response_model=list[PlantAliasRead])
def list_aliases(plant_id: uuid.UUID | None = Query(default=None), db: Session = Depends(get_db)):
    return service.list_aliases(db, plant_id=plant_id)


@router.get("/plants/{plant_id}", response_model=PlantRead)
def get_plant(plant_id: uuid.UUID, db: Session = Depends(get_db)):
    return service.get_plant_or_404(db, plant_id)


@router.patch("/plants/{plant_id}", response_model=PlantRead)
def update_plant(plant_id: uuid.UUID, payload: PlantUpdate, db: Session = Depends(get_db)):
    plant = service.update_plant(db, plant_id, payload)
    db.commit()
    return plant


# ---- Coal Companies ----
@router.post("/coal-companies", response_model=CoalCompanyRead, status_code=status.HTTP_201_CREATED)
def create_coal_company(payload: CoalCompanyCreate, db: Session = Depends(get_db)):
    company = service.create_coal_company(db, payload)
    db.commit()
    return company


@router.get("/coal-companies", response_model=Page[CoalCompanyRead])
def list_coal_companies(page_params: PageParams = Depends(), db: Session = Depends(get_db)):
    items, total = service.list_coal_companies(db, limit=page_params.page_size, offset=page_params.offset)
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)


# ---- Suppliers ----
@router.post("/suppliers", response_model=SupplierRead, status_code=status.HTTP_201_CREATED)
def create_supplier(payload: SupplierCreate, db: Session = Depends(get_db)):
    supplier = service.create_supplier(db, payload)
    db.commit()
    return supplier


@router.get("/suppliers", response_model=Page[SupplierRead])
def list_suppliers(page_params: PageParams = Depends(), db: Session = Depends(get_db)):
    items, total = service.list_suppliers(db, limit=page_params.page_size, offset=page_params.offset)
    return Page(items=items, page=page_params.page, page_size=page_params.page_size, total=total)
