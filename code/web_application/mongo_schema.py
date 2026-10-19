"""Pydantic request and response models for the HW6 MongoDB API."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class InspectionStatus(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    WARNING = "WARNING"


class InspectionCategory(str, Enum):
    ROUTINE = "Routine"
    COMPLAINT = "Complaint"
    FOLLOW_UP = "Follow-up"


class DocumentCreate(BaseModel):
    inspection_code: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    status: InspectionStatus = InspectionStatus.WARNING
    category: InspectionCategory
    inspection_date: datetime

    @field_validator("inspection_code")
    @classmethod
    def clean_code(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("inspection_code cannot be empty")
        return value

    @field_validator("description")
    @classmethod
    def clean_description(cls, value: str | None) -> str | None:
        if value is None:
            return None
        value = value.strip()
        return value or None


class DocumentUpdate(DocumentCreate):
    pass


class DocumentResponse(DocumentCreate):
    id: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)
