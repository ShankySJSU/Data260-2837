import json
import traceback
import requests
import subprocess
import hashlib
import time
import os

PORT_BASE = 8137
SID4 = 2837
SEED = 2837
VERIFY_SEED = 260000 + SID4

'''
Before running validation checks. Please ensure the following are running:
1. Ensure the database is running (MySQL)
2. FAST API
uvicorn hw4_main:app --port 8137
3. React Frontend (must be in react directory to execute the following command)
npm run dev
4. ollama 
5. Run this verification script
'''
checks = []

def run_check(name, fn):
    try:
        result = fn()
        checks.append({"check": name, "status": "PASS" if result else "FAIL"})
    except Exception:
        traceback.print_exc()
        checks.append({"check": name, "status": "FAIL"})

# 1 – Check backend is running
def check_backend_running():
    try:
        r = requests.get(f"http://localhost:{PORT_BASE}/")
        return r.status_code == 200
    except:
        return False

# 2 – Check main inspection endpoint (Get)
#http://localhost:8137/inspection/    
def check_inspection_list():
      s = requests.Session()
      s.post(f"http://localhost:{PORT_BASE}/login",
             params={"email": "test1@sjsu.edu", "password": "test123"})
      r = s.get(f"http://localhost:{PORT_BASE}/inspection/")
      return r.status_code == 200 and isinstance(r.json(), list)

# 3 – Check login functionality (POST)
#http://localhost:8137/login?email=test1@sjsu.edu&password=test123
def check_login():
    try:
        r = requests.post(
            f"http://localhost:{PORT_BASE}/login",
            params={"email": "test1@sjsu.edu", "password": "test123"}
        )
        return r.status_code == 200
    except:
        return False

# 4 – Check /me authentication
#http://localhost:8137/me
def check_me():
    try:
        s = requests.Session()
        # login first
        login = s.post(
            f"http://localhost:{PORT_BASE}/login",
            params={"email": "test1@sjsu.edu", "password": "test123"}
        )
        if login.status_code != 200:
            return False
        r = s.get(f"http://localhost:{PORT_BASE}/me")
        return r.status_code == 200 and "status" in r.json()
    except:
        return False

# Run tests
run_check("backend_running", check_backend_running)
run_check("login", check_login)
run_check("me_authenticated", check_me)
run_check("inspection_list", check_inspection_list)

'''
# Obtain Git commit hash
try:
    commit_hash = (
        subprocess.check_output(["git", "rev-parse", "HEAD"])
        .decode("utf-8")
        .strip()
    )
except:
    commit_hash = "UNKNOWN"
'''

verification = {
    "homework": "HW4",
    "sid4": SID4,
    "seed": SEED,
    "verify_seed": VERIFY_SEED,
    "port": PORT_BASE,
    # "commit_hash": commit_hash,
    "model": "sentence-transformers/all-MiniLM-L6-v2 + local Ollama models",
    "checks": checks,
}

file_path = "../../reports/hw04/verification.json"
# Ensure that the directory path exists; if not, create it
os.makedirs(os.path.dirname(file_path), exist_ok=True)

# Open the file and dump the JSON data
with open(file_path, "w") as f:
    json.dump(verification, f, indent=4)


print("verification.json created successfully.")