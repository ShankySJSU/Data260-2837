import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from code.hw2_graph import run_graph


INPUT_PATH = "reports/hw02/cases/schema_input.json"

input_data = json.load(open(INPUT_PATH))
title = input_data["title"]
content = input_data["content"]

def clean(result):
    safe = dict(result)
    safe.pop("llm", None)
    return safe

def run_with_ceiling(ceiling):
    results = []
    for _ in range(20):
        start = time.time()
        r = clean(run_graph(title, content, max_turns=ceiling))
        end = time.time()
        results.append({"success": r.get("success", False), "latency": end - start})
    return results

if __name__ == "__main__":
    c2 = run_with_ceiling(2)
    c10 = run_with_ceiling(10)

    final = {
        "ceiling_2": c2,
        "ceiling_10": c10
    }

    json.dump(final, open("reports/hw02/raw/ceiling_compare.json", "w"), indent=2)
    print("Ceiling comparison results saved in JSON file. ceiling_compare")