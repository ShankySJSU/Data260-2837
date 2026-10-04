from fastapi import FastAPI, Depends, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import event
import hashlib

from database import get_db, Base, engine, query_counter
from domain.session_manager import (
    create_session,
    validate_session,
    delete_session,
)
from domain.router import router as domain_router
from domain.models import User


# ============================================================
# DATA260 HW5 CONFIGURATION
# ============================================================

PORT_BASE = 8137
SID4 = 2837
SEED = SID4
VERIFY_SEED = 260000 + SID4


# ============================================================
# SQL QUERY COUNTER
# ============================================================

def before_cursor_execute(
    conn,
    cursor,
    statement,
    parameters,
    context,
    executemany,
):
    query_counter["count"] += 1


# Prevent duplicate event listeners during development reloads
if not getattr(engine, "_hw5_query_listener_added", False):
    event.listen(
        engine,
        "before_cursor_execute",
        before_cursor_execute,
    )
    engine._hw5_query_listener_added = True


# ============================================================
# DATABASE INITIALIZATION
# ============================================================

# All SQLAlchemy models must be imported before this line.
# The import from domain.models above registers the models.
Base.metadata.create_all(bind=engine)


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="DATA260 HW5 Backend",
    version="1.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# AUTHENTICATION DEPENDENCY
# ============================================================

def require_login(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Validate the HTTP-only session cookie.

    All protected domain endpoints use this dependency.
    """
    token = request.cookies.get("session_token")

    if not token:
        raise HTTPException(
            status_code=401,
            detail="Login required",
        )

    user_id = validate_session(db, token)

    if not user_id:
        raise HTTPException(
            status_code=401,
            detail="Session expired or invalid",
        )

    return user_id


# ============================================================
# LOGIN
# ============================================================

@app.post("/login")
def login(
    email: str,
    password: str,
    db: Session = Depends(get_db),
):
    """
    Authenticate a user and create an HTTP-only session cookie.
    """
    user = (
        db.query(User)
        .filter(User.email == email)
        .first()
    )

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    # Existing HW4 password verification method.
    # Passwords are not stored as plain text.
    hashed_password = hashlib.sha256(
        password.encode("utf-8")
    ).hexdigest()

    if hashed_password != user.password_hash:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials",
        )

    session_token = create_session(
        db,
        user.id,
    )

    response = JSONResponse(
        content={
            "message": "Login successful",
            "user_id": user.id,
        }
    )

    response.set_cookie(
        key="session_token",
        value=session_token,
        httponly=True,
        max_age=1800,
        samesite="lax",
        secure=False,  # False for localhost development
    )

    return response


# ============================================================
# LOGOUT
# ============================================================

@app.post("/logout")
def logout(
    request: Request,
    db: Session = Depends(get_db),
):
    """
    Delete the server-side session and remove the browser cookie.
    """
    token = request.cookies.get("session_token")

    if token:
        delete_session(db, token)

    response = JSONResponse(
        content={
            "message": "Logged out",
        }
    )

    response.delete_cookie(
        key="session_token",
    )

    return response


# ============================================================
# AUTHENTICATION CHECK
# ============================================================

@app.get("/me")
def me(
    user_id: int = Depends(require_login),
):
    return {
        "user_id": user_id,
        "status": "authenticated",
    }


# ============================================================
# PROTECTED HW5 DOMAIN ROUTES
# ============================================================

app.include_router(
    domain_router,
    dependencies=[
        Depends(require_login),
    ],
)


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "message": "DATA260 HW5 Backend Running",
        "port": PORT_BASE,
        "homework": "Shashank-HW5",
    }
# testing