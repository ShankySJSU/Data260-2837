import time
import csv
import os
import requests

BASE_URL = "http://localhost:8137/inspection"
LOGIN_URL = "http://localhost:8137/login"
PAGE_SIZES = [10, 50, 200]
VERSIONS = ["naive", "fixed"]

#since this file is in code/web_application/domain/n_plus_one_test.py, the output file path is relative to this file's location
#hence i am using "../../../reports/hw04/raw/n_plus_one_raw.csv" to go up three directories and then into the reports/hw04/raw/ folder
OUTPUT_FILE = "../../../reports/hw04/raw/n_plus_one_raw.csv"

def measure():
    rows = []
    session = requests.Session()

    # Log in first so the session cookie is attached to every subsequent request
    login_resp = session.post(f"{LOGIN_URL}?email=test1@sjsu.edu&password=test123")
    if login_resp.status_code != 200:
        print("Login failed:", login_resp.status_code, login_resp.text)
        return
    print("Login successful, starting benchmark...")

    for version in VERSIONS:
        for size in PAGE_SIZES:
            for run in range(30):
                url = f"{BASE_URL}/{version}?page=1&page_size={size}"
                start = time.time()
                response = session.get(url)
                end = time.time()

                elapsed = (end - start) * 1000  # ms

                if response.status_code == 200:
                    sql_count = response.json().get("sql_queries", None)
                else:
                    sql_count = None
                    print(f"Request failed: {version} size={size} run={run} status={response.status_code}")

                rows.append([version, size, run, elapsed, sql_count])

    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["version", "page_size", "run", "latency_ms", "sql_queries"])
        writer.writerows(rows)

    print("Benchmark completed, saved results to", OUTPUT_FILE)


if __name__ == "__main__":
    measure()