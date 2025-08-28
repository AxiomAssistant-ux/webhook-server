import json
from copy import deepcopy
from datetime import datetime, timezone
from zoneinfo import ZoneInfo  # Python 3.9+
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from config import LAST_PAYLOAD
from helper import (
    save_json_safe,
    append_summary,
    to_str,
    to_str_list,
)
from db import connect_to_mongo, close_mongo_connection, get_database

app = FastAPI()


def ts_to_datetime(ts, tz_name="UTC"):
    """
    Convert a Unix timestamp (s/ms/ns) to a timezone-aware datetime.
    Auto-detects seconds vs milliseconds vs nanoseconds.
    """
    # Coerce to float
    t = float(ts)

    # Heuristic unit detection
    if t > 1e14:      # nanoseconds range
        t /= 1_000_000_000.0
    elif t > 1e11:    # milliseconds range
        t /= 1_000.0
    # else: assume seconds

    # Make a UTC datetime, then convert to requested TZ
    dt_utc = datetime.fromtimestamp(t, tz=timezone.utc)
    return dt_utc.astimezone(ZoneInfo(tz_name))


@app.on_event("startup")
async def startup_event():
    await connect_to_mongo()


@app.on_event("shutdown")
async def shutdown_event():
    await close_mongo_connection()


def serialize_doc(doc: dict) -> dict:
    d = dict(doc)
    _id = d.get("_id")
    if _id is not None:
        d["_id"] = str(_id)
    return d


@app.post("/end-call-webhook")
async def end_call_webhook(request: Request):
    # Read body
    body = await request.body()
    try:
        parsed = json.loads(body.decode("utf-8"))
    except json.JSONDecodeError:
        parsed = {"raw_text": body.decode("utf-8", errors="replace")}

    # Debug snapshot (ephemeral on Heroku)
    save_json_safe(LAST_PAYLOAD, {"headers": dict(request.headers), "body": deepcopy(parsed)})

    # ----- DIRECT EXTRACTION FROM KNOWN STRUCTURE -----
    # Extract from the actual structure in the JSON
    data_section = parsed.get("data", {})
    analysis_section = data_section.get("analysis", {})
    data_collection = analysis_section.get("data_collection_results", {})
    metadata = data_section.get("metadata", {})
    
    # Direct extraction using exact keys from the JSON structure
    name_raw = data_collection.get("caller_name", {}).get("value")
    email_raw = data_collection.get("Caller Email", {}).get("value")
    phone_raw = data_collection.get("caller_number", {}).get("value")
    
    brief_raw = data_collection.get("brief_summary", {}).get("value")
    detailed_raw = data_collection.get("Detailed Summary", {}).get("value")
    
    questions_raw = data_collection.get("questions_asked", {}).get("value")
    actions_raw = data_collection.get("Action Items", {}).get("value")
    
    # Extract new fields using exact paths
    agent_id_raw = data_section.get("agent_id")
    recording_raw = None  # Not present in current structure, but ready for future
    
    # Extract call timing from exact metadata paths
    call_start_timestamp = metadata.get("start_time_unix_secs")
    call_duration = metadata.get("call_duration_secs")
    
    # Fallback to event_timestamp if metadata not available
    if not call_start_timestamp:
        call_start_timestamp = parsed.get("event_timestamp")

    # Coerce to the final schema (strings + string[])
    caller_name = to_str(name_raw)
    caller_email = to_str(email_raw)
    caller_number = to_str(phone_raw)

    # Format call timing using timestamp conversion
    call_timing = ""
    if call_start_timestamp:
        try:
            # Convert to both UTC and Pakistan time
            dt_utc = ts_to_datetime(call_start_timestamp, "UTC")
            dt_pk = ts_to_datetime(call_start_timestamp, "Asia/Karachi")
            
            utc_str = dt_utc.strftime("%A, %d %b %Y, %H:%M:%S %Z")
            pk_str = dt_pk.strftime("%A, %d %b %Y, %H:%M:%S %Z")
            
            call_timing = f"Start: {utc_str} | {pk_str}"
            
            # Add duration if available
            if call_duration:
                call_timing += f" | Duration: {call_duration}s"
        except Exception:
            # Fallback for timestamp issues
            call_timing = f"Timestamp: {call_start_timestamp}"
    else:
        call_timing = "No timing data available"

    brief_summary = to_str(brief_raw)
    detailed_summary = to_str(detailed_raw)

    questions_list = to_str_list(questions_raw)
    actions_list = to_str_list(actions_raw)
    
    # Process new fields
    agent_id = to_str(agent_id_raw)
    recording_link = to_str(recording_raw)

    summary_obj = {
        "Caller Name": caller_name,
        "Caller Email": caller_email,
        "Caller Number": caller_number,
        "Agent ID": agent_id,
        "Recording Link": recording_link,
        "Call timing": call_timing,
        "Brief Summary": brief_summary,
        "Detailed Summary": detailed_summary,
        "Questions asked during call": questions_list,
        "Action Items": actions_list,
    }

    # Insert → returns inserted_id (string)
    try:
        inserted_id = await append_summary(summary_obj)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save summary: {e!s}")

    return JSONResponse(content={
        "status": "success",
        "inserted_id": inserted_id,
        "saved": deepcopy(summary_obj),
    })


@app.get("/summary")
async def get_summaries(limit: int = 50, skip: int = 0):
    try:
        db = get_database()
        cursor = db.summaries.find({}).sort("_id", -1).skip(skip).limit(limit)
        summaries_list = []
        async for doc in cursor:
            summaries_list.append(serialize_doc(doc))
        return {"summaries": summaries_list}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read summaries: {e!s}")
