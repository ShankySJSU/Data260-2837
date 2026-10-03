from datetime import datetime
from enum import Enum
import re

from pydantic import BaseModel, Field, field_validator

class InspectionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class RestaurantBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    address: str = Field(..., min_length=3, max_length=500)
    permit_code: str = Field(..., min_length=4, max_length=50)

    @field_validator("name", "address")
    @classmethod
    def validate_text(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Value cannot be empty")

        return value

    @field_validator("permit_code")
    @classmethod
    def validate_permit_code(cls, value):
        value = value.strip().upper()

        if not re.fullmatch(r"[A-Z0-9-]{4,50}", value):
            raise ValueError(
                "permit_code must contain only uppercase letters, "
                "numbers, and hyphens"
            )

        return value


class RestaurantCreate(RestaurantBase):
    pass


class RestaurantUpdate(RestaurantBase):
    pass


class RestaurantResponse(RestaurantBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class InspectionBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=255)
    inspection_code: str = Field(..., min_length=8, max_length=50)
    inspection_date: datetime
    status: InspectionStatus
    score: int = Field(default=0, ge=0, le=100)
    restaurant_id: int = Field(..., gt=0)

    @field_validator("status", mode="before")
    @classmethod
    def normalize_status(cls, value):
        if isinstance(value, str):
            value = value.strip().upper()

        try:
            return InspectionStatus(value)
        except ValueError:
            raise ValueError(
                "status must be PASS, FAIL, or WARNING"
            )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()

        if not value:
            raise ValueError("Inspection name cannot be empty")

        return value


class InspectionCreate(InspectionBase):
    pass


class InspectionUpdate(InspectionBase):
    pass


class InspectionResponse(InspectionBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        orm_mode = True


class Related(BaseModel):
    id: int
    details: str | None = None
    inspection_id: int

    class Config:
        orm_mode = True


# Compatibility name for older HW4 code
Inspection = InspectionResponse