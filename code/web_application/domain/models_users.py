from sqlalchemy import Column, Integer, String, Enum
from web_application.database import Base

class AuthUser(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(50), unique=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    role = Column(Enum("reader", "writer", "moderator"), nullable=False)