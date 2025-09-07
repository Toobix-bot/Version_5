from __future__ import annotations
from pathlib import Path
import orjson
from typing import Dict, Any, List

SCENARIO_DIR = Path("scenarios")
ITEM_DIR = Path("items")

def load_scenario(name: str = "default") -> Dict[str, Any]:  # pragma: no cover simple IO
    p = SCENARIO_DIR / f"{name}.json"
    if not p.exists():
        return {"name": name, "need_drift": {}, "event_bias": {}}
    try:
        return orjson.loads(p.read_bytes())
    except Exception:
        return {"name": name, "need_drift": {}, "event_bias": {}}

def load_items_pack(file: str = "starter_pack.json") -> List[Dict[str, Any]]:  # pragma: no cover
    p = ITEM_DIR / file
    if not p.exists():
        return []
    try:
        return orjson.loads(p.read_bytes())
    except Exception:
        return []
