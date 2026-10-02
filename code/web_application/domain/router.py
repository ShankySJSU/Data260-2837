from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload
from database import get_db, query_counter
from .import crud, schema
from .models import (
    InspectionRelated,
    Restaurant,
    RestaurantInspection,
)


router = APIRouter(
    tags=["HW5 Domain API"],
)


# ============================================================
# RESTAURANT ROUTES
# ============================================================

@router.get(
    "/restaurants/",
    response_model=list[schema.RestaurantResponse],
)
def list_restaurants(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    return crud.list_restaurants(
        db,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/restaurants/",
    response_model=schema.RestaurantResponse,
    status_code=201,
)
def create_restaurant(
    data: schema.RestaurantCreate,
    db: Session = Depends(get_db),
):
    return crud.create_restaurant(
        db,
        data,
    )


@router.get(
    "/restaurants/{restaurant_id}",
    response_model=schema.RestaurantResponse,
)
def get_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_restaurant(
        db,
        restaurant_id,
    )


@router.put(
    "/restaurants/{restaurant_id}",
    response_model=schema.RestaurantResponse,
)
def update_restaurant(
    restaurant_id: int,
    data: schema.RestaurantUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_restaurant(
        db,
        restaurant_id,
        data,
    )


@router.delete(
    "/restaurants/{restaurant_id}",
)
def delete_restaurant(
    restaurant_id: int,
    db: Session = Depends(get_db),
):
    return crud.delete_restaurant(
        db,
        restaurant_id,
    )


@router.get(
    "/restaurants/{restaurant_id}/inspections",
    response_model=list[schema.InspectionResponse],
)
def get_restaurant_inspections(
    restaurant_id: int,
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    return crud.inspections_for_restaurant(
        db,
        restaurant_id,
        page=page,
        page_size=page_size,
    )


# ============================================================
# INSPECTION ROUTES
# ============================================================

@router.get(
    "/inspection/",
    response_model=list[schema.InspectionResponse],
)
def list_inspections(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=100,
    ),
    db: Session = Depends(get_db),
):
    return crud.list_inspections(
        db,
        page=page,
        page_size=page_size,
    )


@router.post(
    "/inspection/",
    response_model=schema.InspectionResponse,
    status_code=201,
)
def create_inspection(
    data: schema.InspectionCreate,
    db: Session = Depends(get_db),
):
    return crud.create_inspection(
        db,
        data,
    )


# These static routes must appear before /inspection/{inspection_id}.
@router.get(
    "/inspection/naive",
)
def list_naive(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    """
    HW4 benchmark endpoint.

    Performs one related-table query per inspection.
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
            .filter(
                InspectionRelated.inspection_id == item.id
            )
            .all()
        )

        output.append(
            {
                "id": item.id,
                "name": item.name,
                "status": item.status,
                "related": [
                    {
                        "id": related_item.id,
                        "details": related_item.details,
                    }
                    for related_item in related
                ],
            }
        )

    return {
        "records": output,
        "sql_queries": query_counter["count"],
    }


@router.get(
    "/inspection/fixed",
)
def list_fixed(
    page: int = Query(
        default=1,
        ge=1,
    ),
    page_size: int = Query(
        default=10,
        ge=1,
        le=500,
    ),
    db: Session = Depends(get_db),
):
    """
    HW4 benchmark endpoint.

    Uses eager loading to avoid the N+1 query problem.
    """
    query_counter["count"] = 0

    offset = (page - 1) * page_size

    items = (
        db.query(RestaurantInspection)
        .options(
            joinedload(
                RestaurantInspection.related_items
            )
        )
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
                    {
                        "id": related_item.id,
                        "details": related_item.details,
                    }
                    for related_item in item.related_items
                ],
            }
        )

    return {
        "records": output,
        "sql_queries": query_counter["count"],
    }


@router.get(
    "/inspection/{inspection_id}",
    response_model=schema.InspectionResponse,
)
def get_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    return crud.get_inspection(
        db,
        inspection_id,
    )


@router.put(
    "/inspection/{inspection_id}",
    response_model=schema.InspectionResponse,
)
def update_inspection(
    inspection_id: int,
    data: schema.InspectionUpdate,
    db: Session = Depends(get_db),
):
    return crud.update_inspection(
        db,
        inspection_id,
        data,
    )


@router.delete(
    "/inspection/{inspection_id}",
)
def delete_inspection(
    inspection_id: int,
    db: Session = Depends(get_db),
):
    return crud.delete_inspection(
        db,
        inspection_id,
    )