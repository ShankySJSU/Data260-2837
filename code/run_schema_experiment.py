import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from code.hw2_graph import run_graph

def clean(result):
    safe = dict(result)
    safe.pop("llm", None)
    return safe

def run_30():
    input_data = json.load(open("reports/hw02/cases/schema_input.json"))
    title = input_data["title"]
    content = input_data["content"]

    stats = {
        "valid_first": 0,
        "valid_one_retry": 0,
        "valid_two_plus": 0,
        "ceiling": 0
    }

    for i in range(30):
        result = clean(run_graph(title, content, max_turns=10))
        turns = result.get("turn_count", 0)
        success = result.get("success", False)

        if success and turns == 1:
            stats["valid_first"] += 1
        elif success and turns == 2:
            stats["valid_one_retry"] += 1
        elif success and turns > 2:
            stats["valid_two_plus"] += 1
        else:
            stats["ceiling"] += 1

    print(stats)
    json.dump(stats, open("reports/hw02/raw/schema_stats.json", "w"), indent=2)

if __name__ == "__main__":
    run_30()