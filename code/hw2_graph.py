"""
Final HW2 LangGraph Implementation (Planner → Reviewer → Supervisor)
This version:
- Works with Python 3.12 (Microsoft Store)
- Works with LangGraph >= 0.1.x (invoke API)
- Works with Ollama model qwen2.5:1.5b
- Cleans JSON from markdown/backticks
- Guarantees planner_output/reviewer_output are valid JSON dicts
- Supports validation rules (3 tags, tag length 3–30 chars, summary <= 25 words)
"""

import json
import re
from typing import TypedDict, Any, Dict
from src.model_client import get_llm, call_llm
from pydantic import BaseModel, ValidationError, Field
from langgraph.graph import StateGraph, END


# ================================================================
# JSON CLEANING — Removes Markdown and extracts valid { ... }
# ================================================================
def extract_json_block(text: str):
    """
    Cleans LLM output and extracts the first valid JSON block.
    Removes ```json fences, markdown, and extra commentary.
    """
    if isinstance(text, dict):
        return text  # Already clean JSON
    
    if not isinstance(text, str):
        return {}

    # Remove markdown fences
    cleaned = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # Try direct load
    try:
        return json.loads(cleaned)
    except:
        pass

    # Try to find JSON block manually
    match = re.search(r"{[\s\S]*}", cleaned)
    if match:
        try:
            return json.loads(match.group())
        except:
            return {}

    return {}


# ================================================================
# AgentState Shared Memory
# ================================================================
class AgentState(TypedDict):
    title: str
    content: str
    llm: Any
    planner_output: Dict[str, Any]
    reviewer_output: Dict[str, Any]
    turn_count: int
    max_turns: int
    success: bool


# ================================================================
# Pydantic Schema Validation
# ================================================================
class PlannerSchema(BaseModel):
    tags: list[str] = Field(min_length=3, max_length=3)
    summary: str

    @classmethod
    def validate_output(cls, output):
        # Missing fields
        if "tags" not in output or "summary" not in output:
            raise ValidationError("Missing required fields")

        # Tag length rules
        for tag in output["tags"]:
            if len(tag) < 3 or len(tag) > 30:
                raise ValidationError("Tag length invalid")

        # Summary word limit
        if len(output["summary"].split()) > 25:
            raise ValidationError("Summary too long")

        return cls(**output)


# ================================================================
# PLANNER NODE
# ================================================================
def planner_node(state: AgentState):
    llm = state["llm"]

    prompt = (
        "You are the Planner agent.\n"
        "Your output MUST be STRICT JSON ONLY. NO markdown, NO backticks.\n"
        "Generate exactly 3 tags (each 3–30 chars) and a summary <= 25 words.\n\n"
        "Return ONLY this JSON structure:\n"
        "{\n"
        "  \"tags\": [\"tag1\", \"tag2\", \"tag3\"],\n"
        "  \"summary\": \"short summary\"\n"
        "}\n\n"
        f"TITLE: {state['title']}\n"
        f"CONTENT: {state['content']}\n"
    )

    raw = call_llm(llm, prompt)
    json_out = extract_json_block(raw)

    return {
        "planner_output": json_out,
        "turn_count": state["turn_count"] + 1
    }


# ================================================================
# REVIEWER NODE
# ================================================================
def reviewer_node(state: AgentState):
    llm = state["llm"]
    planner_json = state["planner_output"]

    prompt = (
        "You are the Reviewer agent.\n"
        "Validate and correct the Planner JSON.\n"
        "Output MUST be STRICT JSON ONLY — no markdown, no backticks.\n\n"
        "Return ONLY this JSON structure:\n"
        "{\n"
        "  \"tags\": [\"tag1\", \"tag2\", \"tag3\"],\n"
        "  \"summary\": \"corrected summary\"\n"
        "}\n\n"
        "Rules:\n"
        "- Exactly 3 tags (3–30 chars)\n"
        "- Summary <= 25 words\n\n"
        "Planner JSON:\n"
        f"{planner_json}\n"
    )

    raw = call_llm(llm, prompt)
    json_out = extract_json_block(raw)

    return {
        "reviewer_output": json_out,
        "turn_count": state["turn_count"] + 1
    }


# ================================================================
# SUPERVISOR NODE — increments the turn counter
# ================================================================
def supervisor_node(state: AgentState):
    return {"turn_count": state["turn_count"] + 1}


# ================================================================
# ROUTER LOGIC
# ================================================================
def router_logic(state: AgentState):
    # First turn -> Planner
    if state["turn_count"] == 0:
        return "planner"

    # Second turn -> Reviewer
    if state["turn_count"] == 1:
        return "reviewer"

    # After Reviewer -> schema validation
    reviewer_json = state.get("reviewer_output", {})

    try:
        PlannerSchema.validate_output(reviewer_json)
        return END
    except:
        if state["turn_count"] >= state["max_turns"]:
            return END
        return "planner"


# ================================================================
# MAIN RUN_GRAPH FUNCTION (LangGraph invoke API)
# ================================================================
def run_graph(title: str, content: str, max_turns: int = 5) -> AgentState:
    llm = get_llm()  # qwen2.5:1.5b recommended

    init_state: AgentState = {
        "title": title,
        "content": content,
        "llm": llm,
        "planner_output": {},
        "reviewer_output": {},
        "turn_count": 0,
        "max_turns": max_turns,
        "success": False
    }

    workflow = StateGraph(AgentState)

    workflow.add_node("planner", planner_node)
    workflow.add_node("reviewer", reviewer_node)
    workflow.add_node("supervisor", supervisor_node)

    workflow.set_entry_point("supervisor")

    workflow.add_conditional_edges("supervisor", router_logic, {
        "planner": "planner",
        "reviewer": "reviewer",
        END: END
    })

    workflow.add_edge("planner", "supervisor")
    workflow.add_edge("reviewer", "supervisor")

    app = workflow.compile()

    final_state = app.invoke(init_state)

    # Final schema validation
    try:
        PlannerSchema.validate_output(final_state["reviewer_output"])
        final_state["success"] = True
    except:
        final_state["success"] = False

    return final_state