# helper.py
import json
import re
from copy import deepcopy
from typing import Any, Iterable, List, Mapping, Optional

from db import get_database


def save_json_safe(path: str, obj: Any):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


async def append_summary(summary_obj: dict) -> str:
    """
    Insert a summary into MongoDB.
    NOTE: caller must provide already-flattened strings/arrays.
    """
    db = get_database()
    doc = deepcopy(summary_obj)  # avoid in-place _id injection
    result = await db.summaries.insert_one(doc)
    return str(result.inserted_id)


# ---------- Extraction utilities ----------

def _walk_values(obj: Any) -> Iterable[tuple[str, Any]]:
    """Yield (lowercased_key, value) pairs recursively for dict/list payloads."""
    if isinstance(obj, Mapping):
        for k, v in obj.items():
            if isinstance(v, (dict, list, tuple)):
                yield from _walk_values(v)
            yield (str(k).lower(), v)
    elif isinstance(obj, (list, tuple)):
        for item in obj:
            yield from _walk_values(item)


def get_first_present(payload: Any, candidate_keys: List[str]) -> Optional[Any]:
    """Return the first value whose KEY matches a candidate (case-insensitive)."""
    wants = {c.lower(): c for c in candidate_keys}
    for k_norm, v in _walk_values(payload):
        if k_norm in wants:
            return v
    return None


# ---------- Coercion to the exact shape you want ----------

_PREFERRED_VALUE_KEYS = (
    "value", "text", "string", "content", "email", "name", "phone", "number"
)

def to_str(x: Any) -> str:
    """Coerce any value (dict/list/number/None) into a clean string."""
    if x is None:
        return ""
    if isinstance(x, (str, int, float, bool)):
        s = str(x).strip()
        return s

    if isinstance(x, Mapping):
        # Prefer common payload shapes: {..., "value": "...", ...}
        for key in _PREFERRED_VALUE_KEYS:
            if key in x:
                s = to_str(x[key])
                if s:
                    return s
        # Otherwise, pick the first non-empty string we can derive from values
        for v in x.values():
            s = to_str(v)
            if s:
                return s
        return ""

    if isinstance(x, (list, tuple)):
        # Return first non-empty scalar string we can find
        for item in x:
            s = to_str(item)
            if s:
                return s
        return ""

    # Fallback
    try:
        return str(x).strip()
    except Exception:
        return ""


_BULLET_SPLITS = [
    r"(?:\r?\n|\r)\s*(?:[\*\-]\s+)",  # - item / * item
    r"(?:\r?\n|\r)\s*\d+\.\s+",       # 1. item
]

def _split_bullets(s: str) -> List[str]:
    s = s.strip()
    if not s:
        return []
    # Try bullets
    for pat in _BULLET_SPLITS:
        parts = re.split(pat, s)
        parts = [p.strip() for p in parts if p and p.strip()]
        if len(parts) > 1:
            return parts
    # Try newlines
    lines = [ln.strip() for ln in re.split(r"\r?\n|\r", s) if ln.strip()]
    if len(lines) > 1:
        return lines
    # Single item
    return [s]


def to_str_list(x: Any) -> List[str]:
    """
    Coerce any value into a list[str].
    - If dict with 'value' key containing list → flatten to strings.
    - If list of dicts/strings → flatten to strings.
    - If string with bullets/newlines → split.
    - Else → [] or single-item list.
    """
    if x is None:
        return []

    if isinstance(x, Mapping):
        # If dict holds a meaningful list in 'value' or common keys
        if "value" in x:
            v = x["value"]
            return to_str_list(v)
        for key in ("items", "list", "questions", "action_items"):
            if key in x:
                return to_str_list(x[key])
        # Fallback: treat as scalar text
        s = to_str(x)
        return _split_bullets(s) if s else []

    if isinstance(x, (list, tuple)):
        out: List[str] = []
        for item in x:
            if isinstance(item, Mapping):
                if "value" in item:
                    out.extend(to_str_list(item["value"]))
                else:
                    s = to_str(item)
                    if s:
                        out.extend(_split_bullets(s))
            else:
                s = to_str(item)
                if s:
                    out.extend(_split_bullets(s))
        # Deduplicate and keep order
        seen = set()
        cleaned = []
        for s in out:
            ss = s.strip()
            if ss and ss not in seen:
                seen.add(ss)
                cleaned.append(ss)
        return cleaned

    if isinstance(x, (str, int, float, bool)):
        return _split_bullets(str(x))

    # Fallback
    s = to_str(x)
    return _split_bullets(s) if s else []
