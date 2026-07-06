import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---- Plant ----
class PlantCreate(BaseModel):
    plant_code: str = Field(min_length=1, max_length=32)
    plant_name: str = Field(min_length=1, max_length=255)
    is_active: bool = True


class PlantUpdate(BaseModel):
    plant_name: str | None = Field(default=None, min_length=1, max_length=255)
    is_active: bool | None = None


class PlantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_code: str
    plant_name: str
    is_active: bool
    created_at: datetime
    updated_at: datetime


# ---- Plant Alias ----
class PlantAliasCreate(BaseModel):
    plant_id: uuid.UUID
    alias_name: str = Field(min_length=1, max_length=255)


class PlantAliasRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    plant_id: uuid.UUID
    alias_name: str
    created_at: datetime


# ---- Coal Company ----
class CoalCompanyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=32)


class CoalCompanyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str | None
    created_at: datetime
    updated_at: datetime


# ---- Supplier ----
class SupplierCreate(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=32)
    coal_company_id: uuid.UUID | None = None


class SupplierRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    code: str | None
    coal_company_id: uuid.UUID | None
    created_at: datetime
    updated_at: datetime
