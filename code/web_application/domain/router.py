from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session, joinedload

from web_application.auth import get_current_user, require_role
from database import get_db, query_counter

from .import crud, schema
from .models import (
    InspectionRelated,
    Restaurant,
    RestaurantInspection,
)

router = APIRouter(
    tags=["HW7 Domain API"],
)

# ============================================================
# RESTAURANT ROUTES (SECURED FOR HW7)
# ============================================================

@router.get(
    "/restaurants/",
    response_model=list[schema.RestaurantResponse],
)
def list_restaurants(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    return crud.list_restaurants(db, page=page, page_size=page_size)


@router.post(
    "/restaurants/",
    response_model=schema.RestaurantResponse,
    status_code=201,
    dependencies=[Depends(require_role("writer", "moderator"))],   # write/mod only
)
def create_restaurant(
    data: schema.RestaurantCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.create_restaurant(db, data)


@router.get(
    "/restaurants/{restaurant_id}",
    response_model=schema.RestaurantResponse,
)
def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    return crud.get_restaurant(db, restaurant_id)


@router.put(
    "/restaurants/{restaurant_id}",
    response_model=schema.RestaurantResponse,
    dependencies=[Depends(require_role("writer", "moderator"))],   # write/mod only
)
def update_restaurant(
    restaurant_id: int,
    data: schema.RestaurantUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.update_restaurant(db, restaurant_id, data)


@router.delete(
    "/restaurants/{restaurant_id}",
    dependencies=[Depends(require_role("moderator"))],   # mod only
)
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.delete_restaurant(db, restaurant_id)


@router.get(
    "/restaurants/{restaurant_id}/inspections",
    response_model=list[schema.InspectionResponse],
)
def get_restaurant_inspections(
    restaurant_id: int,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    return crud.inspections_for_restaurant(
        db, restaurant_id, page=page, page_size=page_size
    )


# ============================================================
# INSPECTION ROUTES (SECURED FOR HW7)
# ============================================================

@router.get(
    "/inspection/",
    response_model=list[schema.InspectionResponse],
)
def list_inspections(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    return crud.list_inspections(db, page=page, page_size=page_size)


@router.post(
    "/inspection/",
    response_model=schema.InspectionResponse,
    status_code=201,
    dependencies=[Depends(require_role("writer", "moderator"))],   # write/mod only
)
def create_inspection(
    data: schema.InspectionCreate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.create_inspection(db, data)


# These static routes must appear before /inspection/{inspection_id}.

@router.get("/inspection/naive")
def list_naive(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    """
    HW4 naive benchmark endpoint.
    """
    query_counter["count"] = 0
    offset = (page - 1) * page_size

    items = (
        db.query(RestaurantInspection)
        .order_by(RestaurantInspection.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    output = []
    for item in items:
        related = (
            db.query(InspectionRelated)
            .filter(InspectionRelated.inspection_id == item.id)
            .all()
        )
        output.append(
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "related": [
                    {"id": r.id, "details": r.details}
                    for r in related
                ],
            }
        )

    return {"records": output, "sql_queries": query_counter["count"]}


@router.get("/inspection/fixed")
def list_fixed(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=500),
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    """
    HW4 eager-loading benchmark endpoint.
    """
    query_counter["count"] = 0
    offset = (page - 1) * page_size

    items = (
        db.query(RestaurantInspection)
        .options(joinedload(RestaurantInspection.related_items))
        .order_by(RestaurantInspection.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )

    output = []
    for item in items:
        output.append(
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "related": [
                    {"id": r.id, "details": r.details}
                    for r in item.related_items
                ],
            }
        )

    return {"records": output, "sql_queries": query_counter["count"]}


@router.get(
    "/inspection/{inspection_id}",
    response_model=schema.InspectionResponse,
)
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),     # any authenticated user
):
    return crud.get_inspection(db, inspection_id)


@router.put(
    "/inspection/{inspection_id}",
    response_model=schema.InspectionResponse,
    dependencies=[Depends(require_role("writer", "moderator"))],   # write/mod only
)
def update_inspection(
    inspection_id: int,
    data: schema.InspectionUpdate,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.update_inspection(db, inspection_id, data)


@router.delete(
    "/inspection/{inspection_id}",
    dependencies=[Depends(require_role("moderator"))],   # mod only
)
def delete_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
    user = Depends(get_current_user),
):
    return crud.delete_inspection(db, inspection_id)