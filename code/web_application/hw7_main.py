from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from web_application.auth import router as auth_router
from web_application.domain.router import router as domain_router
from web_application.mongo_routes import router as mongo_router
from web_application.memory_routes import router as memory_router

from web_application.mongo_db import ensure_mongodb_schema
from web_application.memory_service import ensure_memory_indexes

#for HW7.
from web_application.domain.models_users import AuthUser  # ensure table creation

# ============================================================
# DATA260 HW7 CONFIGURATION
# ============================================================

PORT_BASE = 8137
SID4 = 2837
SEED = SID4
VERIFY_SEED = 260000 + SID4


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="DATA260 HW7 Backend",
    version="1.0.0",
)


# ============================================================
# CORS CONFIGURATION
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================
# ROUTERS (JWT SECURED)
# ============================================================

app.include_router(auth_router)      # /auth/login, /auth/me
app.include_router(domain_router)    # restaurant inspection domain
app.include_router(mongo_router)     # HW6 document API
app.include_router(memory_router)    # HW6 memory routes


# ============================================================
# STARTUP TASKS
# ============================================================

@app.on_event("startup")
def initialize_hw7_backend():
    ensure_mongodb_schema()
    ensure_memory_indexes()


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/")
def root():
    return {
        "message": "DATA260 HW7 Backend Running",
        "port": PORT_BASE,
        "homework": "Shashank-HW7",
    }