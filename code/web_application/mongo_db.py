"""MongoDB connection and schema setup for DATA260 HW6."""

import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from pymongo import ASCENDING, DESCENDING, MongoClient

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.getenv("MONGO_DB_NAME", "s2837_doc")
DOCUMENT_COLLECTION = "inspections"

mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
mongo_db = mongo_client[MONGO_DB_NAME]
documents = mongo_db[DOCUMENT_COLLECTION]


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def ensure_mongodb_schema() -> None:
    """Create the HW6 database collection and MongoDB-side validation."""
    validator = {
        "$jsonSchema": {
            "bsonType": "object",
            "required": [
                "inspection_code",
                "status",
                "category",
                "inspection_date",
                "created_at",
                "updated_at",
            ],
            "properties": {
                "inspection_code": {
                    "bsonType": "string",
                    "minLength": 1,
                    "maxLength": 100,
                },
                "description": {
                    "bsonType": ["string", "null"],
                },
                "status": {
                    "enum": ["PASS", "FAIL", "WARNING"],
                },
                "category": {
                    "enum": ["Routine", "Complaint", "Follow-up"],
                },
                "inspection_date": {
                    "bsonType": "date",
                },
                "created_at": {
                    "bsonType": "date",
                },
                "updated_at": {
                    "bsonType": "date",
                },
            },
        }
    }

    existing = mongo_db.list_collection_names()
    if DOCUMENT_COLLECTION not in existing:
        mongo_db.create_collection(
            DOCUMENT_COLLECTION,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )
    else:
        mongo_db.command(
            "collMod",
            DOCUMENT_COLLECTION,
            validator=validator,
            validationLevel="strict",
            validationAction="error",
        )

    documents.create_index(
        [("inspection_code", ASCENDING)],
        unique=True,
        name="uq_inspection_code",
    )
    documents.create_index(
        [("inspection_date", DESCENDING)],
        name="inspection_date_desc",
    )
