import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from bson import ObjectId
from typing import List, Optional

from database import db, create_document, get_documents
from schemas import Task

app = FastAPI(title="Pastel Pro To-Do API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Pastel Pro To-Do API is running"}

# Helpers

def serialize_task(doc: dict) -> dict:
    return {
        "id": str(doc.get("_id")),
        "title": doc.get("title"),
        "description": doc.get("description"),
        "completed": doc.get("completed", False),
        "priority": doc.get("priority"),
        "due_date": doc.get("due_date").isoformat() if doc.get("due_date") else None,
        "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
        "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None,
    }

# CRUD Endpoints for tasks

@app.post("/api/tasks", response_model=dict)
async def create_task(task: Task):
    try:
        inserted_id = create_document("task", task)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/tasks", response_model=List[dict])
async def list_tasks(q: Optional[str] = None, completed: Optional[bool] = None):
    try:
        filter_dict = {}
        if q:
            # Simple case-insensitive substring search on title
            filter_dict["title"] = {"$regex": q, "$options": "i"}
        if completed is not None:
            filter_dict["completed"] = completed
        docs = get_documents("task", filter_dict)
        return [serialize_task(d) for d in docs]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class TaskUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    completed: Optional[bool] = None
    priority: Optional[str] = None
    due_date: Optional[str] = None  # ISO string

@app.patch("/api/tasks/{task_id}")
async def update_task(task_id: str, payload: TaskUpdate):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        update_doc = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if "due_date" in update_doc and update_doc["due_date"] is None:
            update_doc["due_date"] = None
        res = db["task"].update_one({"_id": ObjectId(task_id)}, {"$set": {**update_doc, "updated_at": __import__('datetime').datetime.now(__import__('datetime').timezone.utc)}})
        if res.matched_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        doc = db["task"].find_one({"_id": ObjectId(task_id)})
        return serialize_task(doc)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: str):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    try:
        res = db["task"].delete_one({"_id": ObjectId(task_id)})
        if res.deleted_count == 0:
            raise HTTPException(status_code=404, detail="Task not found")
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
