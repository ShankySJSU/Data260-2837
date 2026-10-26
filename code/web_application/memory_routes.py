"""FastAPI endpoints for HW6 MongoDB-backed memory."""

import sys
from pathlib import Path


from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from web_application.memory_service import (
    EPISODES,
    MESSAGES,
    SUMMARIES,
    ensure_memory_indexes,
    process_chat,
)

from file_memory import handle_file_command

# AGENT.md and MEMORY.md intentionally live at repository root. Add that root
# to the import path because the existing HW5 launch command runs from this
# web_application directory.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))



router = APIRouter(prefix="/api", tags=["HW6 Memory"])


class ChatRequest(BaseModel):
    user_id: str = Field(..., min_length=1, max_length=100)
    session_id: str | None = Field(default=None, max_length=100)
    message: str = Field(..., min_length=1, max_length=4000)


@router.post("/chat")
def chat(payload: ChatRequest):
    if payload.message.strip().startswith("/"):
        return {"session_id": payload.session_id, "file_memory": handle_file_command(payload.message, payload.user_id, payload.session_id)}
    try:
        return process_chat(payload.user_id.strip(), payload.session_id, payload.message.strip())
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Local model or memory error: {exc}")


@router.get("/memory/{user_id}")
def memory(user_id: str):
    messages = list(
        MESSAGES.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(16)
    )
    summaries = list(
        SUMMARIES.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(20)
    )
    episodes = list(
        EPISODES.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(20)
    )
    return {
        "user_id": user_id,
        "messages": list(reversed(messages)),
        "latest_session_summary": next((s for s in summaries if s.get("scope") == "session"), None),
        "latest_lifetime_summary": next((s for s in summaries if s.get("scope") == "user"), None),
        "episodes": episodes,
    }


@router.post("/memory-command")
def memory_command(payload: ChatRequest):
    return handle_file_command(payload.message, payload.user_id, payload.session_id)


@router.get("/aggregate/{user_id}")
def aggregate(user_id: str):
    pipeline = [
        {"$match": {"user_id": user_id}},
        {"$group": {
            "_id": {"$dateToString": {"format": "%Y-%m-%d", "date": "$created_at"}},
            "message_count": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]
    daily = list(MESSAGES.aggregate(pipeline))
    recent_summaries = list(
        SUMMARIES.find({"user_id": user_id}, {"_id": 0})
        .sort("created_at", -1)
        .limit(10)
    )
    return {
        "user_id": user_id,
        "daily_message_counts": [
            {"date": item["_id"], "message_count": item["message_count"]} for item in daily
        ],
        "recent_summaries": recent_summaries,
    }


@router.on_event("startup")
def initialize_memory_indexes():
    ensure_memory_indexes()
