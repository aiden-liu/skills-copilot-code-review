"""
Announcements management endpoints.

Public GET /announcements returns active announcements.
Management endpoints require `teacher_username` to be provided and valid.
"""
from fastapi import APIRouter, HTTPException, Body, Query
from typing import Optional, List, Dict, Any
from datetime import datetime
from bson.objectid import ObjectId

from ..database import announcements_collection, teachers_collection

router = APIRouter(
    prefix="/announcements",
    tags=["announcements"]
)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": str(doc.get("_id")),
        "message": doc.get("message"),
        "start_date": doc.get("start_date").isoformat() if doc.get("start_date") else None,
        "end_date": doc.get("end_date").isoformat() if doc.get("end_date") else None,
        "created_by": doc.get("created_by"),
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
    }


@router.get("", response_model=List[Dict[str, Any]])
def get_active_announcements() -> List[Dict[str, Any]]:
    """Return announcements that are currently active (end_date >= now and start_date <= now or not set)"""
    now = datetime.utcnow()
    query = {
        "end_date": {"$gte": now},
        "$or": [
            {"start_date": None},
            {"start_date": {"$lte": now}},
            {"start_date": {"$exists": False}},
        ],
    }

    results = []
    for doc in announcements_collection.find(query).sort([("end_date", 1)]):
        results.append(_serialize(doc))

    return results


@router.get("/all", response_model=List[Dict[str, Any]])
def get_all_announcements(teacher_username: str = Query(...)) -> List[Dict[str, Any]]:
    """Return all announcements. Requires a valid teacher username."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    results = []
    for doc in announcements_collection.find().sort([("end_date", 1)]):
        results.append(_serialize(doc))

    return results


@router.post("", response_model=Dict[str, Any])
def create_announcement(
    message: str = Body(...),
    end_date: str = Body(...),
    start_date: Optional[str] = Body(None),
    teacher_username: str = Body(...),
):
    """Create a new announcement. `end_date` required (ISO date or YYYY-MM-DD)."""
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    # Parse dates
    try:
        end_dt = datetime.fromisoformat(end_date)
    except Exception:
        try:
            end_dt = datetime.fromisoformat(end_date + "T00:00:00")
        except Exception:
            raise HTTPException(status_code=400, detail="Invalid end_date format")

    start_dt = None
    if start_date:
        try:
            start_dt = datetime.fromisoformat(start_date)
        except Exception:
            try:
                start_dt = datetime.fromisoformat(start_date + "T00:00:00")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid start_date format")

    doc = {
        "message": message,
        "start_date": start_dt,
        "end_date": end_dt,
        "created_by": teacher_username,
        "created_at": datetime.utcnow(),
    }

    result = announcements_collection.insert_one(doc)
    doc["_id"] = result.inserted_id

    return _serialize(doc)


@router.put("/{announcement_id}", response_model=Dict[str, Any])
def update_announcement(
    announcement_id: str,
    message: Optional[str] = Body(None),
    end_date: Optional[str] = Body(None),
    start_date: Optional[str] = Body(None),
    teacher_username: str = Body(...),
):
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    update = {}
    if message is not None:
        update["message"] = message
    if end_date is not None:
        try:
            update["end_date"] = datetime.fromisoformat(end_date)
        except Exception:
            try:
                update["end_date"] = datetime.fromisoformat(end_date + "T00:00:00")
            except Exception:
                raise HTTPException(status_code=400, detail="Invalid end_date format")
    if start_date is not None:
        if start_date == "":
            update["start_date"] = None
        else:
            try:
                update["start_date"] = datetime.fromisoformat(start_date)
            except Exception:
                try:
                    update["start_date"] = datetime.fromisoformat(start_date + "T00:00:00")
                except Exception:
                    raise HTTPException(status_code=400, detail="Invalid start_date format")

    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = announcements_collection.update_one({"_id": oid}, {"$set": update})
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    doc = announcements_collection.find_one({"_id": oid})
    return _serialize(doc)


@router.delete("/{announcement_id}")
def delete_announcement(announcement_id: str, teacher_username: str = Query(...)):
    teacher = teachers_collection.find_one({"_id": teacher_username})
    if not teacher:
        raise HTTPException(status_code=401, detail="Invalid teacher credentials")

    try:
        oid = ObjectId(announcement_id)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid announcement id")

    result = announcements_collection.delete_one({"_id": oid})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Announcement not found")

    return {"message": "Announcement deleted"}
