from fastapi import FastAPI, Depends, Request, Response, HTTPException, Cookie
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from sqlalchemy.orm import Session

from .database import get_db, Base, engine
from .session_manager import create_session, validate_session, delete_session
from .domain.router import router as inspection_router
from .domain.models import User

import hashlib


# ----------------------------
# Initialize DB (create tables)
# ----------------------------
Base.metadata.create_all(bind=engine)


# ----------------------------
# FastAPI application
# ----------------------------
app = FastAPI(title="DATA260 HW4 Backend")


# ----------------------------
# CORS (React app)
# ----------------------------
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],   # React dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------
# Helper - Check login status using HTTP-only session cookie
# ---------------------------------------------------------
def require_login(
    request: Request,
    db: Session = Depends(get_db),
):
    token = request.cookies.get("session_token")
    if not token:
        raise HTTPException(status_code=401, detail="Login required")

    user_id = validate_session(db, token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid")

    return user_id   # parent routes can use this


# ----------------------------
# LOGIN ENDPOINT
# ----------------------------
@app.post("/login")
def login(request: Request, response: Response, email: str, password: str, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    hashed = hashlib.sha256(password.encode()).hexdigest()

    if hashed != user.password_hash:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    # create new session token
    token = create_session(db, user.id)

    # set HTTP-only cookie
    response = JSONResponse(content={"message": "Login successful"})
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=1800,      # 30 min
        samesite="Lax",
    )
    return response


# ----------------------------
# LOGOUT ENDPOINT
# ----------------------------
@app.post("/logout")
def logout(request: Request, db: Session = Depends(get_db)):
    token = request.cookies.get("session_token")
    if token:
        delete_session(db, token)

    response = JSONResponse(content={"message": "Logged out"})
    response.delete_cookie("session_token")
    return response


# ----------------------------
# Protected Test Route
# ----------------------------
@app.get("/me")
def me(user_id: int = Depends(require_login)):
    return {"user_id": user_id, "status": "authenticated"}


# ----------------------------
# Mount domain CRUD router
# ----------------------------
app.include_router(
    inspection_router,
    dependencies=[Depends(require_login)]   # protect all CRUD operations
)


# ----------------------------
# ROOT (simple health check)
# ----------------------------
@app.get("/")
def root():
    return {"message": "DATA260 HW4 Backend Running", "port": 8137}