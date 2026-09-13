from typing import TypedDict, Any, Dict
from langchain_ollama import OllamaLLM
from langgraph.graph import StateGraph

# HW2 AgentState
class AgentState(TypedDict):
    title: str
    content: str
    llm: Any
    planner_output: Dict[str, Any]
    reviewer_output: Dict[str, Any]
    turn_count: int
    max_turns: int
    error: str

# LLM loader
def get_llm(model_name="qwen3:4b", temperature=0.0):
    return OllamaLLM(model=model_name, temperature=temperature)

# -------------------------------
# Planner Node
# -------------------------------
def planner_node(state: AgentState):
    llm = state["llm"]
    prompt = f"""
You are the Planner agent.
- respond using only bullet points
- tags must be: Premises Cleanliness, Food Safety, Staff Hygiene
- summary must be <= 25 words

Title: {state['title']}
Content: {state['content']}

Return:
- tags: ["Premises Cleanliness", "Food Safety", "Staff Hygiene"]
- summary: <25 words>
"""
    resp = llm.invoke(prompt)
    return {"planner_output": {"raw": resp}}

# -------------------------------
# Reviewer Node
# -------------------------------
def reviewer_node(state: AgentState):
    llm = state["llm"]
    planner_text = state["planner_output"]["raw"]
    prompt = f"""
You are the Reviewer agent.
- respond using only bullet points
- ensure tags match fixed set
- ensure summary <= 25 words

Planner Output:
{planner_text}

Return:
- tags: ["Premises Cleanliness", "Food Safety", "Staff Hygiene"]
- summary: <corrected summary>
"""
    resp = llm.invoke(prompt)
    return {"reviewer_output": {"raw": resp}}

# -------------------------------
# Supervisor Node
# -------------------------------
def supervisor_node(state: AgentState):
    return {"turn_count": state["turn_count"] + 1}

# -------------------------------
# Router Logic
# -------------------------------
def router_logic(state: AgentState):
    if state["turn_count"] >= state["max_turns"]:
        return "__end__"

    reviewer_raw = state.get("reviewer_output", {}).get("raw", "")
    if reviewer_raw and len(reviewer_raw.split()) <= 25:
        return "__end__"
    else:
        return "planner"

# -------------------------------
# Build Graph
# -------------------------------
def build_graph():
    graph = StateGraph(AgentState)

    graph.add_node("planner", planner_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("supervisor", supervisor_node)

    graph.set_entry_point("planner")

    graph.add_edge("planner", "reviewer")
    graph.add_edge("reviewer", "supervisor")

    graph.add_conditional_edges("supervisor", router_logic)

    return graph.compile()

# -------------------------------
# Runner
# -------------------------------
def run_graph(title, content, max_turns=10):
    llm = get_llm()
    workflow = build_graph()

    initial_state = {
        "title": title,
        "content": content,
        "llm": llm,
        "planner_output": {},
        "reviewer_output": {},
        "turn_count": 0,
        "max_turns": max_turns,
        "error": ""
    }

    for event in workflow.stream(initial_state):
        print("EVENT:", event)