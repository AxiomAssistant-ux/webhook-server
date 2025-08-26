import json
from copy import deepcopy
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse

from config import LAST_PAYLOAD
from helper import (
    save_json_safe,
    append_summary,
    get_first_present,
    to_str,
    to_str_list,
)
from db import connect_to_mongo, close_mongo_connection, get_database

app = FastAPI()


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

    # Candidate keys
    candidates_name = ["caller_name", "name", "caller", "full_name", "Caller Name", "caller name"]
    candidates_email = ["caller_email", "email", "user_email", "Caller Email", "caller email"]
    candidates_phone = ["caller_number", "phone", "phone_number", "Caller Number", "caller number"]

    candidates_start = ["call_start_time", "start_time", "start", "start_time_unix_secs"]
    candidates_end = ["call_end_time", "end_time", "end", "end_time_unix_secs"]

    candidates_brief = ["brief_summary", "brief", "summary", "Brief Summary", "brief summary"]
    candidates_detailed = [
        "detailed_summary",
        "detailed",
        "transcript_summary",
        "Detailed Summary",
        "detailed summary",
    ]
    candidates_questions = [
        "questions_asked",
        "questions",
        "data_questions",
        "Questions Asked",
        "questions asked",
        "Questions asked during call",
    ]
    candidates_actions = [
        "action_items",
        "actions",
        "Action Items",
        "action items",
    ]

    # ----- EXACT SHAPE ENFORCEMENT -----
    name_raw = get_first_present(parsed, candidates_name)
    email_raw = get_first_present(parsed, candidates_email)
    phone_raw = get_first_present(parsed, candidates_phone)

    start_raw = get_first_present(parsed, candidates_start)
    end_raw = get_first_present(parsed, candidates_end)

    brief_raw = get_first_present(parsed, candidates_brief)
    detailed_raw = get_first_present(parsed, candidates_detailed)

    questions_raw = get_first_present(parsed, candidates_questions)
    actions_raw = get_first_present(parsed, candidates_actions)

    # Coerce to the final schema (strings + string[])
    caller_name = to_str(name_raw)
    caller_email = to_str(email_raw)
    caller_number = to_str(phone_raw)

    call_timing = " - ".join([s for s in (to_str(start_raw), to_str(end_raw)) if s]).strip()

    brief_summary = to_str(brief_raw)
    detailed_summary = to_str(detailed_raw)

    questions_list = to_str_list(questions_raw)
    actions_list = to_str_list(actions_raw)

    summary_obj = {
        "Caller Name": caller_name,
        "Caller Email": caller_email,
        "Caller Number": caller_number,
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
