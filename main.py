# main.py
import json
from fastapi import FastAPI, Request, HTTPException

from config import SUMMARY_FILE, LAST_PAYLOAD, WEBHOOK_SECRET
from helper import (
        save_json_safe, 
        append_summary, 
        verify_signature_if_present, 
        get_first_present,
        normalize_questions,
        get_first_present,
        normalize_questions
    )
app1 = FastAPI()


@app1.post("/end-call-webhook")
async def end_call_webhook(request: Request):
    # read raw body and headers
    body = await request.body()
    headers = dict(request.headers)

    # save raw payload for debugging
    try:
        parsed = json.loads(body.decode("utf-8"))
    except Exception:
        # not json -> store raw text
        parsed = {"raw_text": body.decode("utf-8", errors="replace")}

    save_json_safe(LAST_PAYLOAD, {"headers": headers, "body": parsed})

    # verify HMAC signature if secret is set
    signature = headers.get("elevenlabs-signature") or headers.get("ElevenLabs-Signature")
    if not verify_signature_if_present(WEBHOOK_SECRET, body, signature):
        raise HTTPException(status_code=403, detail="Invalid signature")

    # attempt to extract fields from many possible key names
    candidates_name = ["caller_name", "Caller Name", "name", "caller", "full_name", "user_name", "user"]
    candidates_email = ["caller_email", "Caller Email", "email", "user_email", "userEmail"]
    candidates_phone = ["caller_number", "Caller Number", "phone", "phone_number", "phoneNumber"]
    candidates_start = ["call_start", "call_start_time", "start_time", "start", "callStart"]
    candidates_end = ["call_end", "call_end_time", "end_time", "end", "callEnd"]
    candidates_brief = ["brief_summary", "brief", "summary", "briefSummary", "Brief Summary"]
    candidates_detailed = ["detailed_summary", "detailed", "detailedSummary", "Detailed Summary", "transcript_summary"]
    candidates_questions = ["questions", "questions_asked", "Questions Asked", "data_questions", "questionsAsked"]
    candidates_actions = ["action_items", "action_items", "Action Items", "actionItems", "actions"]

    # Extract with the improved function
    caller_name = get_first_present(parsed, candidates_name) or ""
    caller_email = get_first_present(parsed, candidates_email) or ""
    caller_phone = get_first_present(parsed, candidates_phone) or ""
    call_start = get_first_present(parsed, candidates_start) or ""
    call_end = get_first_present(parsed, candidates_end) or ""
    brief = get_first_present(parsed, candidates_brief) or ""
    detailed = get_first_present(parsed, candidates_detailed) or ""
    
    # Handle questions specially since they might be structured differently
    raw_questions = get_first_present(parsed, candidates_questions)
    raw_actions = get_first_present(parsed, candidates_actions)

    questions = normalize_questions(raw_questions)
    actions = normalize_questions(raw_actions) if raw_actions else []

    # Build final summary object with consistent keys
    summary_obj = {
        "Caller Name": caller_name,
        "Caller Email": caller_email, 
        "Caller Number": caller_phone,
        "Call timing": f"{call_start} - {call_end}".strip(" - "),
        "Brief Summary": brief,
        "Detailed Summary": detailed,
        "Questions asked during call": questions,
        "Action Items": actions
    }

    append_summary(summary_obj)
    print("Saved summary:", summary_obj)

    return {"status": "success", "saved": summary_obj}