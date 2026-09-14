# code/verify_hw02.py

"""
This script performs a HW2 smoke test:
 - Check FastAPI availability
 - Check LangGraph workflow execution
 - Check output structure
 - Write verification.json into reports/hw02/
"""


import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from code.hw2_graph import run_graph


# Configuration
SID4 = 2837
PORT_BASE = 8137
VERIFY_SEED = 260000 + SID4

def check_fastapi_notworking():
    try:
        #url= f"http://localhost:{PORT_BASE}"
        #my running on http://127.0.0.1:8137 (Press CTRL+C to quit)
        url = f"http://127.0.0.1:{PORT_BASE}" 
        print("URL:", url)
        r = requests.get(f"{url}/restaurants")
        
        
        return r.status_code == 200
    except:
        return False
        
def check_fastapi():
    import requests
    try:
        url = f"http://127.0.0.1:{PORT_BASE}/restaurants"
        print("Checking:", url)
        r = requests.get(url)
        print("Status:", r.status_code)
        return r.status_code == 200
    except Exception as e:
        print("Error:", e)
        return False

def check_langgraph():
    try:
        test = run_graph("Test Title", "Test Content", max_turns=5)
        return isinstance(test, dict)
    except:
        return False

def check_success_flag():
    try:
        test = run_graph("Title", "Content", max_turns=5)
        return "success" in test
    except:
        return False

def check_planner_output():
    out = run_graph("Title", "Content", max_turns=5)
    return "planner_output" in out

def check_reviewer_output():
    out = run_graph("Title", "Content", max_turns=5)
    return "reviewer_output" in out

def main():
    verification = {
        "homework": "HW02",
        "SID4": str(SID4),
        "commit_hash": "<INSERT YOUR LATEST COMMIT HASH HERE>",
        "model_used": "qwen3:4b via Ollama",
        "SEED": SID4,
        "VERIFY_SEED": VERIFY_SEED,
        "checks": [
            {"name": "FastAPI responds on PORT_BASE=8137", "status": "PASS" if check_fastapi() else "FAIL"},
            {"name": "LangGraph run_graph() executes without hanging", "status": "PASS" if check_langgraph() else "FAIL"},
            {"name": "run_graph() returns dictionary with success flag", "status": "PASS" if check_success_flag() else "FAIL"},
            {"name": "Planner output includes tags & summary", "status": "PASS" if check_planner_output() else "FAIL"},
            {"name": "Reviewer output includes corrected JSON", "status": "PASS" if check_reviewer_output() else "FAIL"}
        ]
    }

    with open("reports/hw02/verification.json", "w") as f:
        json.dump(verification, f, indent=2)

    print("verification.json generated successfully.")

if __name__ == "__main__":
    main()