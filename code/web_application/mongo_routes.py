"""FastAPI CRUD routes for the HW6 MongoDB document view."""

from bson import ObjectId
from fastapi import APIRouter, HTTPException, status
from pymongo.errors import DuplicateKeyError, PyMongoError

from web_application.mongo_db import documents, ensure_mongodb_schema, utc_now
from web_application.mongo_schema import DocumentCreate, DocumentResponse, DocumentUpdate

router = APIRouter(prefix="/api/documents", tags=["HW6 MongoDB Documents"])


def parse_id(document_id: str) -> ObjectId:
    if not ObjectId.is_valid(document_id):
        raise HTTPException(status_code=400, detail="Invalid MongoDB document id")
    return ObjectId(document_id)


def serialize(document: dict) -> dict:
    document["id"] = str(document.pop("_id"))
    return document


def to_response(document: dict) -> DocumentResponse:
    return DocumentResponse.model_validate(serialize(document))


@router.post("", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
def create_document(payload: DocumentCreate):
    now = utc_now()
    document = payload.model_dump(mode="python")
    document.update({"created_at": now, "updated_at": now})

    try:
        result = documents.insert_one(document)
        created = documents.find_one({"_id": result.inserted_id})
        return to_response(created)
    except DuplicateKeyError:
        raise HTTPException(
            status_code=409,
            detail="inspection_code already exists",
        )
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {exc}")


@router.get("", response_model=list[DocumentResponse])
def list_documents():
    try:
        return [to_response(doc) for doc in documents.find().sort("inspection_date", -1)]
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {exc}")


@router.get("/{document_id}", response_model=DocumentResponse)
def get_document(document_id: str):
    object_id = parse_id(document_id)
    document = documents.find_one({"_id": object_id})
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return to_response(document)


@router.put("/{document_id}", response_model=DocumentResponse)
def update_document(document_id: str, payload: DocumentUpdate):
    object_id = parse_id(document_id)
    update = payload.model_dump(mode="python")
    update["updated_at"] = utc_now()

    try:
        result = documents.update_one({"_id": object_id}, {"$set": update})
        if result.matched_count == 0:
            raise HTTPException(status_code=404, detail="Document not found")
        return to_response(documents.find_one({"_id": object_id}))
    except DuplicateKeyError:
        raise HTTPException(status_code=409, detail="inspection_code already exists")
    except PyMongoError as exc:
        raise HTTPException(status_code=500, detail=f"MongoDB error: {exc}")


@router.delete("/{document_id}")
def delete_document(document_id: str):
    object_id = parse_id(document_id)
    result = documents.delete_one({"_id": object_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Document not found")
    return {"message": "Document deleted successfully", "id": document_id}


@router.get("/schema/status")
def schema_status():
    """Reapply the validator and return a simple setup confirmation."""
    ensure_mongodb_schema()
    return {"database": documents.database.name, "collection": documents.name}
