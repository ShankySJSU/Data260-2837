from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from . import crud, schema

router = APIRouter(prefix="/inspection", tags=["inspections"])

@router.get("/")
def list_all(db: Session = Depends(get_db)):
    return crud.get_all(db)

@router.get("/{id}")
def get_by_id(id: int, db: Session = Depends(get_db)):
    return crud.get_one(db, id)

@router.post("/")
def create(data: schema.InspectionCreate, db: Session = Depends(get_db)):
    return crud.create_record(db, data)

@router.put("/{id}")
def update(id: int, data: schema.InspectionUpdate, db: Session = Depends(get_db)):
    return crud.update_record(db, id, data)

@router.delete("/{id}")
def delete(id: int, db: Session = Depends(get_db)):
    return crud.delete_record(db, id)