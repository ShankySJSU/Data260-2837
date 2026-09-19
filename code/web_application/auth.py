#this is my authentical router file (auth.py)
from fastapi import APIRouter, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates
from starlette.status import HTTP_302_FOUND
import time

router = APIRouter()

# Templates directory
templates = Jinja2Templates(directory="code/web_application/templates")

# Hardcoded credentials (HW3 requirement)
VALID_USERNAME = "admin"
VALID_PASSWORD = "password"

# Idle session timeout (seconds)
IDLE_TIMEOUT = 120   # 2 minutes for demo; TA may ask for longer

# -------------------------------
# HOME PAGE
# -------------------------------
@router.get("/")
def home(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "user": user
        }
    )

# -------------------------------
# LOGIN PAGE (GET)
# -------------------------------
@router.get("/login")
def login_page(request: Request):
    user = request.session.get("user")
    return templates.TemplateResponse(
        "login.html",
        {
            "request": request,
            "user": user
        }
    )

# -------------------------------
# LOGIN (POST)
# -------------------------------
@router.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    if username == VALID_USERNAME and password == VALID_PASSWORD:
        # Store session
        request.session["user"] = username
        request.session["last_active"] = time.time()

        return RedirectResponse(
            url="/dashboard",
            status_code=HTTP_302_FOUND
        )

    # invalid credentials → show Bootstrap alert
    return RedirectResponse(
        url="/login?error=1",
        status_code=HTTP_302_FOUND
    )

# -------------------------------
# DASHBOARD (Protected)
# -------------------------------
@router.get("/dashboard")
def dashboard(request: Request):
    user = request.session.get("user")
    last_active = request.session.get("last_active")

    # 1. No user → redirect with expired flag
    if not user:
        return RedirectResponse(
            url="/?expired=1",
            status_code=HTTP_302_FOUND
        )

    # 2. Check idle timeout
    now = time.time()
    if last_active and now - last_active > IDLE_TIMEOUT:
        request.session.clear()
        return RedirectResponse(
            url="/?expired=1",
            status_code=HTTP_302_FOUND
        )

    # 3. Update last active timestamp
    request.session["last_active"] = now

    # 4. Render dashboard
    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user
        }
    )

# -------------------------------
# LOGOUT
# -------------------------------
@router.get("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse(
        url="/",
        status_code=HTTP_302_FOUND
    )