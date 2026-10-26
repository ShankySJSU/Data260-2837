"""
HW7 smoke test; run while the HW7 backend is running.
"""

import os
from pathlib import Path

import requests

# -----------------------------
# CONFIGURATION
# -----------------------------
BASE_URL = os.getenv("HW7_BASE_URL", "http://localhost:8137")
REPO_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = REPO_ROOT / "reports" / "hw07"
OUTPUT = REPORT_DIR / "verification.json"

SID4 = 2837
SEED = SID4
VERIFY_SEED = 260000 + SID4


checks = []


# -----------------------------
# helper to record results
# -----------------------------
def check(name, fn):
    try:
        passed = bool(fn())
        checks.append({"check": name, "status": "PASS" if passed else "FAIL"})
        return passed
    except Exception as exc:
        checks.append(
            {"check": name, "status": "FAIL", "error": str(exc)}
        )
        return False


# -----------------------------
# INDIVIDUAL CHECKS
# -----------------------------

def backend_running():
    return requests.get(f"{BASE_URL}/", timeout=5).status_code == 200


def jwt_login_works():
    """Test /auth/login and /auth/me with seeded user mod1:test123."""
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "mod1", "password": "test123"},
        timeout=5
    )
    if r.status_code != 200:
        return False

    token = r.json().get("token")
    if not token:
        return False

    # Test /auth/me with Bearer token
    r2 = requests.get(
        f"{BASE_URL}/auth/me",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5
    )
    if r2.status_code != 200:
        return False

    data = r2.json()
    return ("username" in data and "role" in data)


def role_writer_can_create():
    """Writer should be able to create a restaurant."""
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "writer1", "password": "test123"},
        timeout=5,
    )
    if r.status_code != 200:
        return False

    token = r.json().get("token", "")
    if not token:
        return False

    payload = {
        "name": "SmokeTest Cafe",
        "address": "Testing Street",
        "permit_code": "SMOKE"
    }

    r2 = requests.post(
        f"{BASE_URL}/restaurants/",
        json=payload,
        headers={"Authorization": f"Bearer {token}"},
        timeout=5
    )

    return r2.status_code in (200, 201)


def role_reader_cannot_delete():
    """Reader should NOT be allowed to delete."""
    r = requests.post(
        f"{BASE_URL}/auth/login",
        json={"username": "reader1", "password": "test123"},
        timeout=5,
    )
    if r.status_code != 200:
        return False

    token = r.json().get("token", "")
    if not token:
        return False

    # Attempt to delete inspection 1 (existing or not)
    r2 = requests.delete(
        f"{BASE_URL}/inspection/1",
        headers={"Authorization": f"Bearer {token}"},
        timeout=5
    )

    return r2.status_code == 403


# -----------------------------
# MAIN
# -----------------------------

def main():
    check("backend_running", backend_running)
    check("jwt_login", jwt_login_works)
    check("writer_create_restaurant", role_writer_can_create)
    check("reader_delete_forbidden", role_reader_cannot_delete)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

