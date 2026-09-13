"""
Minimal HW1-compatible agents_demo.py
This file exists ONLY for reproducibility.
Homework 2 uses hw2_graph.py instead.
"""

import json
from src.model_client import get_llm

def planner_agent(title, content, llm):
    prompt = f"""
    You are the Planner agent.
    Produce exactly 3 topical tags and a summary of <= 25 words.

    TITLE: {title}
    CONTENT: {content}
    """
    return llm.invoke(prompt)


def reviewer_agent(planner_json, llm):
    prompt = f"""
    You are the Reviewer agent.
    Validate planner output.

    Fix if needed:
    - exactly 3 tags
    - tags between 3 and 30 characters
    - summary <= 25 words

    Planner output:
    {planner_json}
    """
    return llm.invoke(prompt)


def run_agents(title, content):
    llm = get_llm()

    planner_response = planner_agent(title, content, llm)
    reviewer_response = reviewer_agent(planner_response, llm)

    return {
        "planner": planner_response,
        "reviewer": reviewer_response
    }


if __name__ == "__main__":
    # Load the HW1 nondeterminism input for reproducibility
    data = json.load(open("reports/hw01/cases/nondeterminism_input.json"))
    title = data["title"]
    content = data["content"]

    result = run_agents(title, content)
    print(json.dumps(result, indent=2))