# code/web_application/hw3_main.py
import json
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
#added the following for Hw3
from starlette.middleware.sessions import SessionMiddleware
from code.web_application.auth import router as auth_router



# ======================================================================
# CONFIGURATION: Based on SID4 = 2837
# ======================================================================
PORT_BASE = 8137  # Required by TA instructions

app = FastAPI()


app.add_middleware(
    SessionMiddleware,
    secret_key="super_secret_key_2837",
    max_age=120,          # match IDLE_TIMEOUT in auth.py
    same_site="lax",
    https_only=False,     # True only if running HTTPS
)


# Include HW3 authentication routes
app.include_router(auth_router)


# Enable CORS for your HTML + JS front-end
#CORS Setting
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
    allow_credentials=True
)

# ======================================================================
# DATA STORAGE FILE
# ======================================================================
DATA_FILE = "restaurants.json"


# Create data file if it does not yet exist
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump([], f)


def load_data():
    """Loads all inspection records from JSON file."""
    with open(DATA_FILE, "r") as f:
        return json.load(f)


def save_data(data):
    """Writes updated list back to JSON file."""
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)


# ======================================================================
# PYDANTIC MODEL FOR RESTAURANT INSPECTIONS
# ======================================================================
class RestaurantInspection(BaseModel):
    restaurantName: str
    restAddress: str
    inspectorEmail: str
    inspectionNotes: str
    inspectionCategory: str
    submittedAt: str


# ======================================================================
# ROUTES REQUIRED FOR HOMEWORK 3
# ======================================================================

# -------------------------------
# 1. LIST ALL RECORDS
# -------------------------------
@app.get("/restaurants")
def get_all():
    return load_data()


# -------------------------------
# 2. ADD NEW RECORD
# -------------------------------
@app.post("/restaurants")
def add_restaurant(rec: RestaurantInspection):
    data = load_data()
    new_id = len(data) + 1

    new_record = {
        "id": new_id,
        "restaurantName": rec.restaurantName,
        "restAddress": rec.restAddress,
        "inspectorEmail": rec.inspectorEmail,
        "inspectionNotes": rec.inspectionNotes,
        "inspectionCategory": rec.inspectionCategory,
        "submittedAt": rec.submittedAt
    }

    data.append(new_record)
    save_data(data)
    return {"message": "Record added", "record": new_record}


# -------------------------------
# 3. UPDATE RECORD WITH passed ID
# -------------------------------
#@app.put("/restaurants/update-1")
#def update_record_one(rec: RestaurantInspection):
@app.put("/restaurants/update/{rec_id}")
def update_record_one(rec_id: int, rec: RestaurantInspection):
    data = load_data()

    for index,item in enumerate(data):
        if item["id"] == rec_id:
            # Construct the dictionary with ID explicitly at the top
            updated_fields = {
                "id": rec_id, ##keeping it original ID
                "restaurantName": rec.restaurantName,
                "restAddress": rec.restAddress,
                "inspectorEmail": rec.inspectorEmail,
                "inspectionNotes": rec.inspectionNotes,
                "inspectionCategory": rec.inspectionCategory,
                "submittedAt": rec.submittedAt
            }
            #now overwrite the data dictionary for this index
            data[index] = updated_fields
            save_data(data)
            statusMsg = f"Resturant ID {rec_id} got updated. Record Details : {item}"
            #return {"message": f"Record ID 1 updated", "record": item}
            return {"message": statusMsg}

    raise HTTPException(status_code=404, detail=f"Record ID {rec_id} was not found in data")


# -------------------------------
# 4. DELETE RECORD WITH HIGHEST ID
# -------------------------------
@app.delete("/restaurants/latest")
def delete_latest():
    data = load_data()
    rec_del = None
    
    if len(data) == 0:
        raise HTTPException(status_code=404, detail="Data set empty. No records to delete")

    #get the maxID from the list
    maxID = max(rec["id"] for rec in data)

    # looping through each dictionary one by one (
    #I am doing this for future, if TA ask me to delee specific record,then my maxID will be the
    #one that is passed to delete , just like update ID
    for rec in data:
        if rec["id"] == maxID:
            rec_del = rec  # Found it! Save the dictionary.
            break          # Stop looking through the rest of the list

    #now loop through the list.. and skip the maxID from the collection
    updated_data = [rec for rec in data if rec["id"] != maxID]

    save_data(updated_data)
    statusMsg = f"Resturant ID {maxID} got deleted. Record Details : {rec_del}"
    return {"message": statusMsg}


# -------------------------------
# 5. SEARCH BY NAME OR ADDRESS
# -------------------------------
@app.get("/restaurants/search")
def search(q: str):
    data = load_data()

    q_lower = q.lower()
    results = [
        item for item in data
        if q_lower in item["restaurantName"].lower()
        or q_lower in item["restAddress"].lower()
    ]

    return {"query": q, "matches": results}