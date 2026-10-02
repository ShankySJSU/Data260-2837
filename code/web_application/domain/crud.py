from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from fastapi import HTTPException

from .models import Restaurant, RestaurantInspection
from . import schema


# ============================================================
# INTERNAL HELPERS
# ============================================================

def validate_pagination(page: int, page_size: int):
    if page < 1:
        raise HTTPException(
            status_code=422,
            detail="page must be greater than or equal to 1",
        )

    if page_size < 1 or page_size > 100:
        raise HTTPException(
            status_code=422,
            detail="page_size must be between 1 and 100",
        )


def commit_or_raise_conflict(db: Session, message: str):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            status_code=409,
            detail=message,
        )


# ============================================================
# RESTAURANT CRUD
# ============================================================

def list_restaurants(
    db: Session,
    page: int = 1,
    page_size: int = 10,
):
    validate_pagination(page, page_size)

    offset = (page - 1) * page_size

    return (
        db.query(Restaurant)
        .order_by(Restaurant.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )


def get_restaurant(
    db: Session,
    restaurant_id: int,
):
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.id == restaurant_id)
        .first()
    )

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail=f"Restaurant {restaurant_id} was not found",
        )

    return restaurant


def create_restaurant(
    db: Session,
    data: schema.RestaurantCreate,
):
    existing = (
        db.query(Restaurant)
        .filter(Restaurant.permit_code == data.permit_code)
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="permit_code already exists",
        )

    restaurant = Restaurant(
        name=data.name,
        address=data.address,
        permit_code=data.permit_code,
    )

    db.add(restaurant)
    commit_or_raise_conflict(
        db,
        "Could not create restaurant because of a constraint violation",
    )
    db.refresh(restaurant)

    return restaurant


def update_restaurant(
    db: Session,
    restaurant_id: int,
    data: schema.RestaurantUpdate,
):
    restaurant = get_restaurant(
        db,
        restaurant_id,
    )

    duplicate = (
        db.query(Restaurant)
        .filter(
            Restaurant.permit_code == data.permit_code,
            Restaurant.id != restaurant_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail="permit_code already belongs to another restaurant",
        )

    restaurant.name = data.name
    restaurant.address = data.address
    restaurant.permit_code = data.permit_code

    commit_or_raise_conflict(
        db,
        "Could not update restaurant because of a constraint violation",
    )
    db.refresh(restaurant)

    return restaurant


def delete_restaurant(
    db: Session,
    restaurant_id: int,
):
    restaurant = get_restaurant(
        db,
        restaurant_id,
    )

    inspection_count = (
        db.query(RestaurantInspection)
        .filter(
            RestaurantInspection.restaurant_id == restaurant_id
        )
        .count()
    )

    if inspection_count > 0:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cannot delete this restaurant because it still has "
                f"{inspection_count} inspection record(s)"
            ),
        )

    db.delete(restaurant)
    commit_or_raise_conflict(
        db,
        "Could not delete restaurant",
    )

    return {
        "message": "Restaurant deleted successfully",
        "id": restaurant_id,
    }


# ============================================================
# INSPECTION CRUD
# ============================================================

def list_inspections(
    db: Session,
    page: int = 1,
    page_size: int = 10,
):
    validate_pagination(page, page_size)

    offset = (page - 1) * page_size

    return (
        db.query(RestaurantInspection)
        .order_by(RestaurantInspection.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )


def get_inspection(
    db: Session,
    inspection_id: int,
):
    inspection = (
        db.query(RestaurantInspection)
        .filter(RestaurantInspection.id == inspection_id)
        .first()
    )

    if inspection is None:
        raise HTTPException(
            status_code=404,
            detail=f"Inspection {inspection_id} was not found",
        )

    return inspection


def create_inspection(
    db: Session,
    data: schema.InspectionCreate,
):
    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.id == data.restaurant_id)
        .first()
    )

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail=f"Restaurant {data.restaurant_id} was not found",
        )

    existing = (
        db.query(RestaurantInspection)
        .filter(
            RestaurantInspection.inspection_code
            == data.inspection_code
        )
        .first()
    )

    if existing:
        raise HTTPException(
            status_code=409,
            detail="inspection_code already exists",
        )

    inspection = RestaurantInspection(
        name=data.name,
        inspection_code=data.inspection_code,
        inspection_date=data.inspection_date,
        status=data.status.value,
        score=data.score,
        restaurant_id=data.restaurant_id,
    )

    db.add(inspection)
    commit_or_raise_conflict(
        db,
        "Could not create inspection because of a constraint violation",
    )
    db.refresh(inspection)

    return inspection


def update_inspection(
    db: Session,
    inspection_id: int,
    data: schema.InspectionUpdate,
):
    inspection = get_inspection(
        db,
        inspection_id,
    )

    restaurant = (
        db.query(Restaurant)
        .filter(Restaurant.id == data.restaurant_id)
        .first()
    )

    if restaurant is None:
        raise HTTPException(
            status_code=404,
            detail=f"Restaurant {data.restaurant_id} was not found",
        )

    duplicate = (
        db.query(RestaurantInspection)
        .filter(
            RestaurantInspection.inspection_code
            == data.inspection_code,
            RestaurantInspection.id != inspection_id,
        )
        .first()
    )

    if duplicate:
        raise HTTPException(
            status_code=409,
            detail=(
                "inspection_code already belongs to another "
                "inspection"
            ),
        )

    inspection.name = data.name
    inspection.inspection_code = data.inspection_code
    inspection.inspection_date = data.inspection_date
    inspection.status = data.status.value
    inspection.score = data.score
    inspection.restaurant_id = data.restaurant_id

    commit_or_raise_conflict(
        db,
        "Could not update inspection because of a constraint violation",
    )
    db.refresh(inspection)

    return inspection


def delete_inspection(
    db: Session,
    inspection_id: int,
):
    inspection = get_inspection(
        db,
        inspection_id,
    )

    db.delete(inspection)
    commit_or_raise_conflict(
        db,
        "Could not delete inspection",
    )

    return {
        "message": "Inspection deleted successfully",
        "id": inspection_id,
    }


def inspections_for_restaurant(
    db: Session,
    restaurant_id: int,
    page: int = 1,
    page_size: int = 10,
):
    # Confirm that the parent restaurant exists.
    get_restaurant(
        db,
        restaurant_id,
    )

    validate_pagination(page, page_size)

    offset = (page - 1) * page_size

    return (
        db.query(RestaurantInspection)
        .filter(
            RestaurantInspection.restaurant_id == restaurant_id
        )
        .order_by(RestaurantInspection.id)
        .offset(offset)
        .limit(page_size)
        .all()
    )


# ============================================================
# HW4 COMPATIBILITY FUNCTIONS
# ============================================================

def get_all(db: Session):
    """
    Compatibility wrapper for the original HW4 router.
    """
    return list_inspections(
        db,
        page=1,
        page_size=100,
    )


def get_one(db: Session, id: int):
    """
    Compatibility wrapper for the original HW4 router.
    """
    return get_inspection(
        db,
        id,
    )


def create_record(db: Session, data):
    """
    Compatibility wrapper for the original HW4 router.
    """
    return create_inspection(
        db,
        data,
    )


def update_record(db: Session, id: int, data):
    """
    Compatibility wrapper for the original HW4 router.
    """
    return update_inspection(
        db,
        id,
        data,
    )


def delete_record(db: Session, id: int):
    """
    Compatibility wrapper for the original HW4 router.
    """
    return delete_inspection(
        db,
        id,
    )