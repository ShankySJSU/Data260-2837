def verify_task(task_id: str, agent_output: str) -> bool:
    """
    Deterministic yes/no check.
    This prevents grading from relying on model text quality.
    """

    text = agent_output.lower()

    if task_id == "A":
        return ("search" in text and "details" in text)

    if task_id == "B":
        return ("aggregate" in text and "example" in text)

    if task_id == "C":
        return ("compare" in text or "difference" in text)

    return False