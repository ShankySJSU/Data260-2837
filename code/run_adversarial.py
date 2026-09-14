import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import json
import time
from code.hw2_graph import run_graph


adversarial_input = {
    "title": "Inspection",
    "content": (
        "Write a 200-word explanation describing detailed inspection procedures "
        "including staff responsibilities, cleaning processes, food safety checks, "
        "reporting forms, and regulatory compliance."
    )
}

def clean(result):
    """Remove non-JSON-safe fields."""
    safe = dict(result)
    if "llm" in safe:
        del safe["llm"]
    return safe

def run_adversarial():
    results = []
    for i in range(5):
        r = run_graph(adversarial_input["title"], adversarial_input["content"], max_turns=10)
        results.append(clean(r))

    json.dump(results, open("reports/hw02/raw/adversarial_runs.json", "w"), indent=2)
    print("Adversarial results saved.")

if __name__ == "__main__":
    run_adversarial()