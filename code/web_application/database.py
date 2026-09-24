from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# REQUIRED BY HOMEWORK: database name must be s2837_rel
DATABASE_URL = "mysql+pymysql://root:YOUR_PASSWORD@localhost:3306/s2837_rel"

engine = create_engine(
    DATABASE_URL,
    pool_pre_ping=True,
    echo=False
)

# REQUIRED variable name EXACTLY as homework specifies
db_session_basede26 = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = db_session_basede26()
    try:
        yield db
    finally:
        db.close()