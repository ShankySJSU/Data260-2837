from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from datetime import datetime, timedelta
import jwt
import bcrypt

from .database import mysql_conn  # your existing DB connector
from web_application.domain.models_users import AuthUser

router = APIRouter()

# ------------------------------
# JWT / SECURITY CONFIG
# ------------------------------
SECRET = "CHANGE_THIS_FOR_PRODUCTION"
ALGORITHM = "HS256"
TOKEN_EXPIRE_MINUTES = 60

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/login")


# ------------------------------
# Pydantic Models
# ------------------------------
class LoginInput(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    token: str
    token_type: str = "bearer"


# ------------------------------
# Password Hashing Utilities
# ------------------------------
def hash_password(password: str) -> str:
    """Hash password using bcrypt."""
    hashed = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt())
    return hashed.decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    """Verify a password against its hash."""
    return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))


# ------------------------------
# JWT Utilities
# ------------------------------
def create_access_token(username: str, role: str):
    expire = datetime.utcnow() + timedelta(minutes=TOKEN_EXPIRE_MINUTES)
    payload = {
        "sub": username,
        "role": role,
        "exp": expire
    }
    return jwt.encode(payload, SECRET, algorithm=ALGORITHM)


def decode_token(token: str):
    """Decode and verify a JWT."""
    try:
        return jwt.decode(token, SECRET, algorithms=[ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Invalid token")


# ------------------------------
# Authentication Dependency
# ------------------------------
def get_current_user(token: str = Depends(oauth2_scheme)):
    payload = decode_token(token)
    return {
        "username": payload["sub"],
        "role": payload["role"]
    }


# ------------------------------
# Role-based Decorator
# ------------------------------
def require_role(*allowed_roles):
    def wrapper(user=Depends(get_current_user)):
        if user["role"] not in allowed_roles:
            raise HTTPException(403, "Forbidden: insufficient role")
        return user
    return wrapper


# ------------------------------
# ROUTE: POST /auth/login --using SQL directly
'''
def login_using_sql(creds: LoginInput):
    conn = mysql_conn()
    cur = conn.cursor(dictionary=True)

    cur.execute("SELECT username, password_hash, role FROM users WHERE username=%s",
                (creds.username,))
    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(creds.password, user["password_hash"]):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(user["username"], user["role"])
    return TokenResponse(token=token)
'''
# ------------------------------

@router.post("/auth/login", response_model=TokenResponse)
def login(creds: LoginInput, db: Session = Depends(get_db)):
    user = (
        db.query(AuthUser)
          .filter(AuthUser.username == creds.username)
          .first()
    )

    if not user:
        raise HTTPException(401, "Invalid credentials")

    if not verify_password(creds.password, user.password_hash):
        raise HTTPException(401, "Invalid credentials")

    token = create_access_token(user.username, user.role)
    return TokenResponse(token=token)

# ------------------------------
# ROUTE: GET /auth/me
# ------------------------------
@router.get("/auth/me")
def auth_me(current = Depends(get_current_user)):
    return current