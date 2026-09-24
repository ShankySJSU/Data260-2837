import json
import requests
from datetime import datetime

VERIFICATION_FILE = "../../reports/hw04/verification.json"
BASE = "http://localhost:8137"

def check(url):
    try:
        r = requests.get(url)
        return r.status_code == 200
    except:
        return False

def main():
    results = {}

    results["home"] = check(f"{BASE}/")
    results["naive"] = check(f"{BASE}/inspection/naive?page=1&page_size=10")
    results["fixed"] = check(f"{BASE}/inspection/fixed?page=1&page_size=10")

    output = {
        "homework": 4,
        "SID4": 2837,
        "commit": "<insert commit hash>",
        "model": "MiniLM-L6-v2",
        "seed": 2837,
        "verify_seed": 262837,
        "checks": results,
        "timestamp": str(datetime.utcnow())
    }

    with open(VERIFICATION_FILE, "w") as f:
        json.dump(output, f, indent=2)

    print("Verification complete.")

if __name__ == "__main__":
    main()