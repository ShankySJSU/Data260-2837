#this is a verification script for hw05.
#  It will check if the backend is running, and will check following
# if the login functionality works, 
# if the /me endpoint is authenticated, 
# and if the inspection list can be retrieved.
#  It will then create a verification.json file with the results of these checks.

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
import importlib.util
import requests


# ============================================================
# PATHS AND CONFIGURATION
# ============================================================

WEB_APP_DIR = Path(__file__).resolve().parent
CODE_DIR = WEB_APP_DIR.parent
REPO_ROOT = CODE_DIR.parent

REPORT_DIR = (
    REPO_ROOT
    / "reports"
    / "hw05"
)

VERIFICATION_FILE = (
    REPORT_DIR
    / "verification.json"
)

MCP_DIR = (
    WEB_APP_DIR
    / "mcp"
)

BASE_URL = "http://localhost:8137"

SID4 = 2837
PORT_BASE = 8137
SEED = 2837
VERIFY_SEED = 262837

MODEL = "qwen2.5:1.5b"


# Make application modules importable.
if str(WEB_APP_DIR) not in sys.path:
    sys.path.insert(0, str(WEB_APP_DIR))


# ============================================================
# CHECK MANAGEMENT
# ============================================================

checks = []


def run_check(
    name,
    function,
):
    try:
        result = function()

        checks.append(
            {
                "check": name,
                "status": (
                    "PASS"
                    if result
                    else "FAIL"
                ),
            }
        )

        return bool(result)

    except Exception as exc:
        checks.append(
            {
                "check": name,
                "status": "FAIL",
                "error": str(exc),
            }
        )

        return False


# ============================================================
# BACKEND CHECKS
# ============================================================

def check_backend_running():
    response = requests.get(
        f"{BASE_URL}/",
        timeout=5,
    )

    return response.status_code == 200


def check_login():
    session = requests.Session()

    response = session.post(
        f"{BASE_URL}/login",
        params={
            "email": "test1@sjsu.edu",
            "password": "test123",
        },
        timeout=5,
    )

    return (
        response.status_code == 200
        and "session_token"
        in session.cookies
    )


def create_authenticated_session():
    session = requests.Session()

    response = session.post(
        f"{BASE_URL}/login",
        params={
            "email": "test1@sjsu.edu",
            "password": "test123",
        },
        timeout=5,
    )

    if response.status_code != 200:
        raise RuntimeError(
            "Login failed while creating test session"
        )

    return session


def check_me_authenticated():
    session = create_authenticated_session()

    response = session.get(
        f"{BASE_URL}/me",
        timeout=5,
    )

    if response.status_code != 200:
        return False

    body = response.json()

    return body.get("status") == "authenticated"


def check_restaurant_list():
    session = create_authenticated_session()

    response = session.get(
        f"{BASE_URL}/restaurants/",
        params={
            "page": 1,
            "page_size": 10,
        },
        timeout=5,
    )

    return (
        response.status_code == 200
        and isinstance(response.json(), list)
    )


def check_inspection_list():
    session = create_authenticated_session()

    response = session.get(
        f"{BASE_URL}/inspection/",
        params={
            "page": 1,
            "page_size": 10,
        },
        timeout=5,
    )

    return (
        response.status_code == 200
        and isinstance(response.json(), list)
    )


# ============================================================
# DOMAIN TOOL CHECK
# ============================================================

def load_local_execute_tool():
    execute_tool_file = (
        MCP_DIR / "execute_tool.py"
    )

    spec = importlib.util.spec_from_file_location(
        "hw5_local_execute_tool",
        execute_tool_file,
    )

    if spec is None or spec.loader is None:
        raise RuntimeError(
            "Could not load local execute_tool.py"
        )

    module = importlib.util.module_from_spec(
        spec
    )


def check_domain_execute_tool():
    probe_code = (
        "import json; "
        "from execute_tool import execute_tool; "
        "print(execute_tool("
        "'search', "
        "{'query': 'Rangoli', 'limit': 1}"
        "))"
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            probe_code,
        ],
        cwd=str(MCP_DIR),
        capture_output=True,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr.strip()
            or result.stdout.strip()
            or "execute_tool failed"
        )

    output_lines = [
        line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]

    if not output_lines:
        raise RuntimeError(
            "execute_tool returned no output"
        )

    payload = json.loads(
        output_lines[-1]
    )

    return (
        payload.get("ok") is True
        and isinstance(
            payload.get("data"),
            list,
        )
        and payload.get("error") is None
    )


# ============================================================
# MCP FILE CHECKS
# ============================================================

def check_meals_server_file():
    server_file = MCP_DIR / "meals_server.py"

    if not server_file.exists():
        return False

    source = server_file.read_text(
        encoding="utf-8"
    )

    required_tools = [
        "search_meals_by_name",
        "meals_by_ingredient",
        "random_meal",
        "meal_details",
    ]

    return all(
        tool_name in source
        for tool_name in required_tools
    )


def check_domain_server_file():
    server_file = MCP_DIR / "domain_server.py"

    if not server_file.exists():
        return False

    source = server_file.read_text(
        encoding="utf-8"
    )

    required_tools = [
        "def search(",
        "def detail_lookup(",
        "def aggregate(",
    ]

    return all(
        tool_signature in source
        for tool_signature in required_tools
    )


def check_python_compilation():
    files = [
        MCP_DIR / "meals_server.py",
        MCP_DIR / "domain_server.py",
        MCP_DIR / "execute_tool.py",
        MCP_DIR / "agent.py",
    ]

    for file_path in files:
        if not file_path.exists():
            return False

        result = subprocess.run(
            [
                sys.executable,
                "-m",
                "py_compile",
                str(file_path),
            ],
            cwd=str(MCP_DIR),
            capture_output=True,
            text=True,
        )

        if result.returncode != 0:
            raise RuntimeError(
                f"Compilation failed for {file_path.name}: "
                f"{result.stderr}"
            )

    return True


# ============================================================
# OFFLINE TEST CHECK
# ============================================================

def check_offline_tests():
    test_file = (
        MCP_DIR
        / "test_execute_tool_offline.py"
    )

    result = subprocess.run(
        [
            sys.executable,
            str(test_file),
        ],
        cwd=str(MCP_DIR),
        capture_output=True,
        text=True,
    )

    print(result.stdout)

    if result.returncode != 0:
        raise RuntimeError(
            result.stderr
            or "Offline tests failed"
        )

    return True


# ============================================================
# GIT COMMIT HASH
# ============================================================

def get_commit_hash():
    try:
        result = subprocess.run(
            [
                "git",
                "rev-parse",
                "HEAD",
            ],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )

        return result.stdout.strip()

    except Exception:
        return "UNKNOWN"


# ============================================================
# RUN VERIFICATION
# ============================================================

run_check(
    "backend_running",
    check_backend_running,
)

run_check(
    "login",
    check_login,
)

run_check(
    "authenticated_me_endpoint",
    check_me_authenticated,
)

run_check(
    "restaurant_list",
    check_restaurant_list,
)

run_check(
    "inspection_list",
    check_inspection_list,
)

run_check(
    "domain_execute_tool",
    check_domain_execute_tool,
)

run_check(
    "meals_server_file",
    check_meals_server_file,
)

run_check(
    "domain_server_file",
    check_domain_server_file,
)

run_check(
    "python_compilation",
    check_python_compilation,
)

run_check(
    "offline_tests",
    check_offline_tests,
)


# ============================================================
# WRITE VERIFICATION JSON
# ============================================================

REPORT_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

verification = {
    "homework": "HW5",
    "sid4": SID4,
    "seed": SEED,
    "verify_seed": VERIFY_SEED,
    "port": PORT_BASE,
    "model": MODEL,
    "commit_hash": get_commit_hash(),
    "generated_at_utc": datetime.now(
        timezone.utc
    ).isoformat(),
    "checks": checks,
}

with VERIFICATION_FILE.open(
    "w",
    encoding="utf-8",
) as file:
    json.dump(
        verification,
        file,
        indent=2,
    )


print()
print(
    "HW5 verification completed."
)
print(
    f"Output written to: {VERIFICATION_FILE}"
)

passed = sum(
    check["status"] == "PASS"
    for check in checks
)

print(
    f"{passed}/{len(checks)} checks passed"
)

if passed != len(checks):
    raise SystemExit(1)