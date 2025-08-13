import json
from typing import Any, List
import re
from db import get_database

def save_json_safe(path: str, obj: Any):
    """Save a JSON object to a file (used for last_payload.json)."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)

def append_summary(summary_obj: dict):
    """Append a summary object to the 'summaries' collection in MongoDB."""
    try:
        db = get_database()
        collection = db.summaries
        collection.insert_one(summary_obj)
        print("Summary appended to MongoDB collection.")
    except Exception as e:
        print(f"Error appending summary to MongoDB: {e}")
        # Decide how to handle DB errors, e.g., retry or log to a fallback file
        raise

def get_first_present(d: dict, candidates: List[str]):
    """Return first non-empty value found among candidate keys (case-insensitive, nested)."""
    if not isinstance(d, dict):
        return None
    
    lowered = {k.lower(): v for k, v in d.items()}
    
    for c in candidates:
        if not c:
            continue
        # Try exact key first
        if c in d:
            return extract_value_from_structured_data(d[c])
        # Then try lowercased key
        if c.lower() in lowered:
            return extract_value_from_structured_data(lowered[c.lower()])
    
    # Check common nested containers
    for container in ("data", "extracted", "extraction", "result", "payload"):
        if container in d and isinstance(d[container], dict):
            val = get_first_present(d[container], candidates)
            if val not in (None, "", []):
                return val

    # Recursively check nested dicts
    for v in d.values():
        if isinstance(v, dict):
            val = get_first_present(v, candidates)
            if val not in (None, "", []):
                return val
    
    return None

def extract_value_from_structured_data(data: Any):
    """Extract the actual value from various data structures."""
    if data is None or data == "":
        return ""
    
    if isinstance(data, (str, int, float, bool)):
        return data
    
    if isinstance(data, dict):
        if 'value' in data and data['value'] not in (None, ""):
            return extract_value_from_structured_data(data['value'])
        for key in ['content', 'text', 'result', 'data']:
            if key in data and data[key] not in (None, ""):
                return extract_value_from_structured_data(data[key])

    if isinstance(data, list):
        return data  # Return list as is for questions/actions
    
    return ""

def normalize_questions(raw: Any) -> List[str]:
    """Convert various question formats into a clean list of strings."""
    if not raw:
        return []
    
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
        
    if isinstance(raw, str):
        # Handle bullet points
        if "*" in raw:
            items = [q.strip() for q in re.split(r'\s*\*\s*', raw) if q.strip()]
            return items
        # Handle numbered lists
        if re.match(r'^\d+\.', raw.strip()):
            items = [q.strip() for q in re.split(r'\d+\.\s*', raw) if q.strip()]
            return items
        # Handle newline-separated
        lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
        if len(lines) > 1:
            return lines
        return [raw.strip()] if raw.strip() else []

    return []