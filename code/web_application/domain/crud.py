from sqlalchemy.orm import Session
from .models import RestaurantInspection

def get_all(db: Session):
    return db.query(RestaurantInspection).all()

def get_one(db: Session, id: int):
    return db.query(RestaurantInspection).filter(RestaurantInspection.id == id).first()

def create_record(db: Session, data):
    obj = RestaurantInspection(name=data.name, status=data.status)
    db.add(obj)
    db.commit()
    db.refresh(obj)
    return obj

def update_record(db: Session, id: int, data):
    obj = get_one(db, id)
    if obj:
        obj.name = data.name
        obj.status = data.status
        db.commit()
        db.refresh(obj)
    return obj

def delete_record(db: Session, id: int):
    obj = get_one(db, id)
    if obj:
        db.delete(obj)
        db.commit()
    return obj