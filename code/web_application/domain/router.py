from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session ,joinedload
from ..database import get_db
from .models import RestaurantInspection, InspectionRelated
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



router = APIRouter(prefix="/inspection", tags=["inspections"])

query_counter["count"] = 0

# ... existing CRUD routes ...

@router.get("/naive")
def list_naive(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    # Pagination (simple)
    offset = (page - 1) * page_size
    items = db.query(RestaurantInspection).offset(offset).limit(page_size).all()

    # N+1: fetch related rows for each parent separately
    output = []
    for item in items:
        related = db.query(InspectionRelated).filter(InspectionRelated.inspection_id == item.id).all()
        output.append({
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "related": [{"id": r.id, "details": r.details} for r in related]
        })

    #fix the code to reunt the records output.. verify later
    '''
    return {
        "records": output,
        "sql_queries": query_counter["count"]
    }
    '''

    return output



@router.get("/fixed")
def list_fixed(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    offset = (page - 1) * page_size

    items = (
        db.query(RestaurantInspection)
          .options(joinedload(RestaurantInspection.related_items))
          .offset(offset)
          .limit(page_size)
          .all()
    )

    output = []
    for item in items:
        output.append({
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "related": [
                {"id": r.id, "details": r.details}
                for r in item.related_items
            ]
        })
    return output