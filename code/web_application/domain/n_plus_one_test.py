import time
import csv
import requests

BASE_URL = "http://localhost:8137/inspection"
PAGE_SIZES = [10, 50, 200]
VERSIONS = ["naive", "fixed"]

OUTPUT_FILE = "../../reports/hw04/raw/n_plus_one_raw.csv"

def measure():
    rows = []

    session = requests.Session()

    for version in VERSIONS:
        for size in PAGE_SIZES:
            for run in range(30):
                url = f"{BASE_URL}/{version}?page=1&page_size={size}"
                start = time.time()
                response = session.get(url)
                end = time.time()

                elapsed = (end - start) * 1000  # ms

                rows.append([version, size, run, elapsed])

    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["version", "page_size", "run", "latency_ms"])
        writer.writerows(rows)

    print("Benchmark completed, saved results to", OUTPUT_FILE)


if __name__ == "__main__":
    measure()