from __future__ import annotations
from pathlib import Path
import orjson
from typing import List, Dict, Any

ACTION_CATALOG_PATH = Path("actions/catalog.json")
EVENT_CATALOG_PATH = Path("events/catalog.json")

class ActionSpec(Dict[str, Any]):
    pass

class EventSpec(Dict[str, Any]):
    pass

def load_actions() -> List[ActionSpec]:  # pragma: no cover simple IO
    if not ACTION_CATALOG_PATH.exists():
        return []
    try:
        return orjson.loads(ACTION_CATALOG_PATH.read_bytes())
    except Exception:
        return []

def load_events() -> Dict[str, EventSpec]:  # pragma: no cover simple IO
    if not EVENT_CATALOG_PATH.exists():
        return {}
    try:
        data = orjson.loads(EVENT_CATALOG_PATH.read_bytes())
        return {e["key"]: e for e in data}
    except Exception:
        return {}
