from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import json
import os

app = FastAPI()

# Enable CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

DATA_FILE = "restaurants.json"

# Create file if it doesn't exist
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)

def load_data():
    with open(DATA_FILE, "r") as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# --------------------------
# Pydantic Model
# --------------------------

class RestaurantInspection(BaseModel):
    restaurantName: str
    restAddress: str
    inspectorEmail: str
    inspectionNotes: str
    inspectionCategory: str
    submittedAt: str

# --------------------------
# Routes Required for HW2
# --------------------------

# 1. LIST ALL
@app.get("/restaurants")
def get_all():
    return load_data()

# 2. ADD NEW ENTRY
@app.post("/restaurants")
def add_restaurant(rec: RestaurantInspection):
    data = load_data()

    next_id = len(data) + 1
    new_rec = rec.dict()
    new_rec["id"] = next_id

    data.append(new_rec)
    save_data(data)
    return {"message": "Record added", "record": new_rec}

# 3. UPDATE RECORD WITH ID = 1
@app.put("/restaurants/update-1")
def update_record_one(rec: RestaurantInspection):
    data = load_data()

    if len(data) == 0:
        raise HTTPException(status_code=404, detail="No records available")

    # Always modify record with id = 1
    data[0].update(rec.dict())
    save_data(data)
    return {"message": "Record #1 updated", "record": data[0]}

# 4. DELETE RECORD WITH HIGHEST ID
@app.delete("/restaurants/latest")
def delete_latest():
    data = load_data()

    if len(data) == 0:
        raise HTTPException(status_code=404, detail="No records to delete")

    deleted = data.pop()
    save_data(data)
    return {"message": "Deleted latest record", "deleted": deleted}

# 5. SEARCH   by restaurantName or restAddress
@app.get("/restaurants/search")
def search(q: str):
    data = load_data()

    res = [
        rec for rec in data
        if q.lower() in rec["restaurantName"].lower()
        or q.lower() in rec["restAddress"].lower()
    ]

