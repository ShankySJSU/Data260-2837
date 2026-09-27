from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session ,joinedload
from database import get_db, query_counter
from .models import RestaurantInspection, InspectionRelated
#from .crud import get_all, get_one, create_record, update_record, delete_record
from . import crud, schema

#shashank explanation to himself..
'''
Q. What is dependency injection?
Ans: Think of it as: "before running this ROUT function, run this other function first, 
and hand me its return value as an argument."
I am using FastAPI's dependency injection system to manage database sessions. 
The `Depends` function allows me to specify that a route function requires a database session, 
which is provided by the `get_db` function. This ensures that each request has its own database session, 
which is properly closed after the request is completed.
'''
query_counter["count"] = 0
router = APIRouter(prefix="/inspection", tags=["inspections"])


#=========================
# All ROUTES methods---------
#========================

@router.get("/")
def list_all(db: Session = Depends(get_db)):
    return crud.get_all(db)

@router.get("/naive")
def list_naive(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    query_counter["count"] = 0   # reset so we only count THIS request's queries

    offset = (page - 1) * page_size
    items = db.query(RestaurantInspection).offset(offset).limit(page_size).all()

    output = []
    for item in items:
        related = db.query(InspectionRelated).filter(InspectionRelated.inspection_id == item.id).all()
        output.append({
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "related": [{"id": r.id, "details": r.details} for r in related]
        })

    return {
        "records": output,
        "sql_queries": query_counter["count"]
    }


@router.get("/fixed")
def list_fixed(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    query_counter["count"] = 0   # reset here too, for a fair comparison

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

    return {
        "records": output,
        "sql_queries": query_counter["count"]
    }


@router.get("/naive")
def list_naive(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    query_counter["count"] = 0   # reset so we only count THIS request's queries

    offset = (page - 1) * page_size
    items = db.query(RestaurantInspection).offset(offset).limit(page_size).all()

    output = []
    for item in items:
        related = db.query(InspectionRelated).filter(InspectionRelated.inspection_id == item.id).all()
        output.append({
            "id": item.id,
            "name": item.name,
            "status": item.status,
            "related": [{"id": r.id, "details": r.details} for r in related]
        })

    return {
        "records": output,
        "sql_queries": query_counter["count"]
    }


@router.get("/fixed")
def list_fixed(db: Session = Depends(get_db), page: int = 1, page_size: int = 10):
    query_counter["count"] = 0   # reset here too, for a fair comparison

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

    return {
        "records": output,
        "sql_queries": query_counter["count"]
    }

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

