import json
from pathlib import Path

from agent import OllamaModel, run_agent


REPO_ROOT = Path(__file__).resolve().parents[3]

RAW_DIR = (
    REPO_ROOT
    / "reports"
    / "hw05"
    / "raw"
)

RAW_DIR.mkdir(
    parents=True,
    exist_ok=True,
)

SUMMARY_FILE = (
    RAW_DIR
    / "agent_scenarios.json"
)

LOG_FILE = (
    RAW_DIR
    / "agent_scenarios.jsonl"
)


SCENARIOS = [
    {
        "name": "search_rangoli",
        "input": (
            "Find all inspections for Rangoli "
            "and summarize their scores and statuses."
        ),
    },
    {
        "name": "inspection_detail",
        "input": (
            "Give me the details for inspection "
            "5006, including its status and score."
        ),
    },
    {
        "name": "pass_aggregate",
        "input": (
            "How many PASS inspections are there "
            "and what is the average score?"
        ),
    },
    {
        "name": "fail_search",
        "input": (
            "Find inspections with FAIL status "
            "and summarize them."
        ),
    },
]


def main():
    model = OllamaModel()
    summaries = []

    # Start a clean scenario log.
    LOG_FILE.write_text(
        "",
        encoding="utf-8",
    )

    for scenario in SCENARIOS:
        print()
        print(
            f"Running scenario: "
            f"{scenario['name']}"
        )

        result = run_agent(
            user_input=scenario["input"],
            model=model,
            max_steps=6,
            log_path=LOG_FILE,
        )

        summary = {
            "scenario": scenario["name"],
            "input": scenario["input"],
            "steps": result["steps"],
            "stop_reason": result[
                "stop_reason"
            ],
            "tool_calls": result[
                "tool_calls"
            ],
            "answer": result.get(
                "answer"
            ),
        }

        summaries.append(summary)

        print(
            json.dumps(
                summary,
                indent=2,
            )
        )

    SUMMARY_FILE.write_text(
        json.dumps(
            summaries,
            indent=2,
        ),
        encoding="utf-8",
    )

    print()
    print(
        "Agent scenarios completed."
    )
    print(
        f"Summary written to: {SUMMARY_FILE}"
    )
    print(
        f"Log written to: {LOG_FILE}"
    )


if __name__ == "__main__":
    main()