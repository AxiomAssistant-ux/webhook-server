import os
import json
import hmac
import hashlib
import re
from typing import Any

from config import SUMMARY_FILE, LAST_PAYLOAD

def save_json_safe(path: str, obj: Any):
    """Save JSON object to a file with UTF-8 encoding."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def save_json_safe(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def append_summary(obj: dict):
    # Ensure summary.json exists and is a list
    if not os.path.exists(SUMMARY_FILE):
        save_json_safe(SUMMARY_FILE, [])
    try:
        with open(SUMMARY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if not isinstance(data, list):
                data = []
    except Exception:
        data = []
    data.append(obj)
    save_json_safe(SUMMARY_FILE, data)

def verify_signature_if_present(secret: str, payload: bytes, signature: str) -> bool:
    # If secret is not set, skip verification (convenience for local testing)
    if not secret:
        print("Warning: WEBHOOK_SECRET not set — skipping signature verification")
        return True
    if not signature:
        return False
    mac = hmac.new(secret.encode("utf-8"), payload, hashlib.sha256).hexdigest()
    return hmac.compare_digest(mac, signature)

def extract_value_from_structured_data(data):
    """
    Extract the actual value from ElevenLabs structured data format.
    Handles both simple values and complex objects with 'value' field.
    """
    if data is None or data == "":
        return ""
    
    # If it's already a simple string/number, return it
    if isinstance(data, (str, int, float, bool)):
        return str(data) if not isinstance(data, str) else data
    
    # If it's a dict with a 'value' field, extract that
    if isinstance(data, dict):
        if 'value' in data:
            value = data['value']
            # Handle nested structure where value might also be an object
            if isinstance(value, dict) and 'value' in value:
                return str(value['value'])
            return str(value) if value not in (None, "") else ""
        
        # If no 'value' field, try to find meaningful content
        # Sometimes the data might be directly in the dict
        for key in ['content', 'text', 'result', 'data']:
            if key in data and data[key] not in (None, ""):
                return str(data[key])
    
    # If it's a list, join the elements
    if isinstance(data, list):
        return data  # Keep as list for questions/actions
    
    return ""

def get_first_present(d: dict, candidates):
    """Return first non-empty value found among candidate keys (case-insensitive, nested)"""
    if not isinstance(d, dict):
        return None
    
    lowered = {k.lower(): v for k, v in d.items()}
    
    for c in candidates:
        if not c:
            continue
        # try exact key
        if c in d:
            return extract_value_from_structured_data(d[c])
        # try lowercased key match
        if c.lower() in lowered:
            return extract_value_from_structured_data(lowered[c.lower()])
    
    # try nested common containers
    for container in ("data", "extracted", "extraction", "data_collection", "result", "payload"):
        if container in d and isinstance(d[container], dict):
            val = get_first_present(d[container], candidates)
            if val not in (None, ""):
                return val
    
    # sometimes payload is a list with dicts or nested objects
    for v in d.values():
        if isinstance(v, dict):
            val = get_first_present(v, candidates)
            if val not in (None, ""):
                return val
    
    return None

def normalize_questions(raw):
    """Convert various question formats into a clean list"""
    if raw is None or raw == "":
        return []
    
    # If it's already a list, clean it up
    if isinstance(raw, list):
        cleaned = []
        for item in raw:
            if isinstance(item, str) and item.strip():
                cleaned.append(item.strip())
        return cleaned
    
    if isinstance(raw, str):
        # Handle bullet-pointed questions
        if raw.startswith("*") or " * " in raw:
            # Split by bullets and clean up
            questions = re.split(r'\s*\*\s*', raw)
            questions = [q.strip() for q in questions if q.strip()]
            return questions
        
        # Handle numbered questions
        if re.match(r'^\d+\.', raw):
            questions = re.split(r'\d+\.\s*', raw)
            questions = [q.strip() for q in questions if q.strip()]
            return questions
        
        # Handle newline-separated questions
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) > 1:
            return lines
        
        # Single question
        if raw.strip():
            return [raw.strip()]
    
    return []