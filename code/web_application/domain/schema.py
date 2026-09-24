from pydantic import BaseModel

class InspectionBase(BaseModel):
    name: str
    status: str

class InspectionCreate(InspectionBase):
    pass

class InspectionUpdate(InspectionBase):
    pass

class Inspection(InspectionBase):
    id: int
    class Config:
        orm_mode = True


class Related(BaseModel):
    id: int
    details: str
    inspection_id: int
    class Config:
        orm_mode = True