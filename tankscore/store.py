from __future__ import annotations
import json, os, datetime
from typing import Any, Dict

def now_ts() -> str:
    return datetime.datetime.utcnow().replace(tzinfo=datetime.timezone.utc).isoformat()

def append_jsonl(path: str, obj: Dict[str, Any]) -> None:
    # ensure dir exists
    d = os.path.dirname(path)
    if d and not os.path.exists(d):
        os.makedirs(d, exist_ok=True)
    with open(path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(obj, ensure_ascii=False) + "\n")

