import json
import time
from agents.hw2_graph import run_graph

adversarial_input = {
    "title": "Inspection",
    "content": (
        "Write a 200-word essay describing detailed inspection procedures "
        "including staff responsibilities, cleaning processes, food safety checks, "
        "reporting forms, and regulatory compliance."
    )
}

def run_adversarial():
    title = adversarial_input["title"]
    content = adversarial_input["content"]

    results = []
    for i in range(5):
        r = run_graph(title, content, max_turns=10)
        results.append(r)

    json.dump(results, open("reports/hw02/raw/adversarial_runs.json", "w"), indent=2)
    print("Adversarial results saved.")

if __name__ == "__main__":
    run_adversarial()