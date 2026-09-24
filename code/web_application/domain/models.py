from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime, timedelta

from ..database import Base

# MAIN DOMAIN ENTITY: restaurant inspection record
class RestaurantInspection(Base):
    __tablename__ = "restaurant_inspection"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    name = Column(String(255), nullable=False)     # primary field
    status = Column(String(255), nullable=False)   # secondary field

    # related rows will be used for N+1 (Part 3)
    related_items = relationship("InspectionRelated")


# RELATED TABLE FOR N+1 (200 rows)
class InspectionRelated(Base):
    __tablename__ = "inspection_related"

    id = Column(Integer, primary_key=True)
    inspection_id = Column(Integer, ForeignKey("restaurant_inspection.id"))
    details = Column(String(255))


# USERS TABLE (login)
class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    name = Column(String(255))
    email = Column(String(255), unique=True, index=True)
    password_hash = Column(String(255))


# SESSIONS TABLE (server-side tokens)
class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(String(255), primary_key=True)          # opaque token
    user_id = Column(Integer, ForeignKey("users.id"))
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime)