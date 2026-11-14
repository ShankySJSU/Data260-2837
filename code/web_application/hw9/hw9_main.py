"""HW9 FastAPI ingress: the domain Q&A endpoint with the semantic cache in front of the HW8
agent pipeline, plus the Part 1 view counter.

    cd code
    python -m uvicorn web_application.hw9_main:app --port 8138
    (8137 is the dockerised HW8 API; HW9 uses PORT_BASE + 1 so both can run)

    POST /qa                     {"query": "...", "threshold": 0.85}
    GET  /inspections/{id}/view  -> increments s2837:views:inspection:<id>
"""

from fastapi import Body, FastAPI, HTTPException

from web_application.hw9 import config as cfg
from web_application.hw9.qa_service import QAService
from web_application.hw9.view_counter import InspectionStore

app = FastAPI(title="DATA260 HW9 - semantic cache (s2837)")
STATE = {}


def service():
    if "qa" not in STATE:
        STATE["qa"] = QAService()
    return STATE["qa"]


@app.get("/")
def root():
    return {"student": cfg.STUDENT_NAME, "prefix": cfg.PREFIX,
            "endpoints": ["POST /qa", "GET /inspections/{id}/view"]}


@app.post("/qa")
def qa(body: dict = Body(...)):
    query = (body.get("query") or "").strip()
    if len(query) < 3:
        raise HTTPException(status_code=422, detail="query must be at least 3 characters")
    res = service().handle(query, threshold=body.get("threshold"))
    return {k: res.get(k) for k in ("query", "answer", "is_cached", "similarity", "latency_ms",
                                    "matched_query", "started_at", "finished_at")}


@app.get("/inspections/{inspection_id}/view")
def view(inspection_id: int):
    if "store" not in STATE:
        STATE["store"] = InspectionStore()
    store = STATE["store"]
    if store.db.get_view_count(inspection_id) is None:
        raise HTTPException(status_code=404, detail="inspection not found")
    return {"inspection_id": inspection_id,
            "views": store.increment_inspection_views(inspection_id)}
