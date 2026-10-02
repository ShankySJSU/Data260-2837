#models.py explictly for homework 5.  It contains the SQLAlchemy models for the
#  restaurant inspection application, 
# including the new fields and relationships required for HW5.
from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import relationship

from database import Base


# ============================================================
# RESTAURANT: RELATED/PARENT ENTITY
# ============================================================

class Restaurant(Base):
    __tablename__ = "restaurant"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    address = Column(
        String(500),
        nullable=False,
    )

    permit_code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    inspections = relationship(
        "RestaurantInspection",
        back_populates="restaurant",
        passive_deletes=True,
    )


# ============================================================
# RESTAURANT INSPECTION: PRIMARY DOMAIN ENTITY
# ============================================================

class RestaurantInspection(Base):
    __tablename__ = "restaurant_inspection"

    id = Column(
        Integer,
        primary_key=True,
        index=True,
        autoincrement=True,
    )

    # Existing HW4 field retained for compatibility
    name = Column(
        String(255),
        nullable=False,
    )

    # New HW5 unique field
    inspection_code = Column(
        String(50),
        unique=True,
        nullable=False,
        index=True,
    )

    inspection_date = Column(
        DateTime,
        nullable=False,
    )

    status = Column(
        String(50),
        nullable=False,
    )

    # Numeric field required by HW5
    score = Column(
        Integer,
        nullable=False,
        default=0,
    )

    # Foreign-key relationship to Restaurant
    restaurant_id = Column(
        Integer,
        ForeignKey(
            "restaurant.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
        index=True,
    )

    created_at = Column(
        DateTime,
        default=datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    updated_at = Column(
        DateTime,
        default=datetime.now(timezone.utc).replace(tzinfo=None),
        onupdate=datetime.now(timezone.utc).replace(tzinfo=None),
        nullable=False,
    )

    restaurant = relationship(
        "Restaurant",
        back_populates="inspections",
    )

    # Existing HW4 relationship retained for N+1 testing
    related_items = relationship(
        "InspectionRelated",
        back_populates="inspection",
        cascade="all, delete-orphan",
    )


# ============================================================
# EXISTING HW4 N+1 TEST ENTITY
# ============================================================

class InspectionRelated(Base):
    __tablename__ = "inspection_related"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    inspection_id = Column(
        Integer,
        ForeignKey(
            "restaurant_inspection.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        index=True,
    )

    details = Column(
        String(255),
        nullable=True,
    )

    inspection = relationship(
        "RestaurantInspection",
        back_populates="related_items",
    )


# ============================================================
# USERS
# ============================================================

class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        autoincrement=True,
    )

    name = Column(
        String(255),
        nullable=False,
    )

    email = Column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )

    password_hash = Column(
        String(255),
        nullable=False,
    )


# ============================================================
# SERVER-SIDE SESSIONS
# ============================================================

class SessionToken(Base):
    __tablename__ = "sessions"

    id = Column(
        String(255),
        primary_key=True,
    )

    user_id = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
    )

    created_at = Column(
        DateTime,
        default=datetime.utcnow,
        nullable=False,
    )

    expires_at = Column(
        DateTime,
        nullable=False,
    )