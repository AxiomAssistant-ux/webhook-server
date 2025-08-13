import json
from fastapi import FastAPI, Request, HTTPException
from bson import ObjectId # Import ObjectId

from config import LAST_PAYLOAD
from helper import (
    save_json_safe,
    append_summary,
    get_first_present,
    normalize_questions,
)
from db import connect_to_mongo, close_mongo_connection, get_database

app = FastAPI()

@app.on_event("startup")
async def startup_event():
    """Connect to MongoDB on application startup."""
    connect_to_mongo()

@app.on_event("shutdown")
async def shutdown_event():
    """Disconnect from MongoDB on application shutdown."""
    close_mongo_connection()

# Helper to convert ObjectId to string for JSON serialization
def serialize_doc(doc):
    doc["_id"] = str(doc["_id"])
    return doc

@app.post("/end-call-webhook")
async def end_call_webhook(request: Request):
    # Read raw body and save for debugging
    body = await request.body()
    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        parsed = {"raw_text": body.decode("utf-8", errors="replace")}
    
    save_json_safe(LAST_PAYLOAD, {"headers": dict(request.headers), "body": parsed})

    # Candidate keys for data extraction
    candidates_name = ["caller_name", "name", "caller", "full_name"]
    candidates_email = ["caller_email", "email", "user_email"]
    candidates_phone = ["caller_number", "phone", "phone_number"]
    candidates_start = ["call_start_time", "start_time", "start"]
    candidates_end = ["call_end_time", "end_time", "end"]
    candidates_brief = ["brief_summary", "brief", "summary"]
    candidates_detailed = ["detailed_summary", "detailed", "transcript_summary"]
    candidates_questions = ["questions_asked", "questions", "data_questions"]
    candidates_actions = ["action_items", "actions"]

    # Extract data using helper functions
    summary_obj = {
        "Caller Name": get_first_present(parsed, candidates_name) or "",
        "Caller Email": get_first_present(parsed, candidates_email) or "",
        "Caller Number": get_first_present(parsed, candidates_phone) or "",
        "Call timing": f"{get_first_present(parsed, candidates_start) or ''} - {get_first_present(parsed, candidates_end) or ''}".strip(" - "),
        "Brief Summary": get_first_present(parsed, candidates_brief) or "",
        "Detailed Summary": get_first_present(parsed, candidates_detailed) or "",
        "Questions asked during call": normalize_questions(get_first_present(parsed, candidates_questions)),
        "Action Items": normalize_questions(get_first_present(parsed, candidates_actions))
    }

    try:
        append_summary(summary_obj)
        print("Saved summary:", summary_obj)
        return {"status": "success", "saved": summary_obj}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save summary: {str(e)}")


@app.get("/summaries")
async def get_summaries():
    """Fetch all summaries from the MongoDB collection."""
    try:
        db = get_database()
        summaries_cursor = db.summaries.find({})
        # Convert cursor to list and serialize ObjectId
        summaries_list = [serialize_doc(doc) for doc in summaries_cursor]
        return {"summaries": summaries_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read summaries: {str(e)}")