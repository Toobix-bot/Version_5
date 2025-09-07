from __future__ import annotations
from pathlib import Path
import orjson
from typing import Any
from .models import PersonaState

DEFAULT_STATE_PATH = Path("state.json")

def save_state(state: PersonaState, path: Path = DEFAULT_STATE_PATH) -> None:
    data = state.model_dump()
    path.write_bytes(orjson.dumps(data, option=orjson.OPT_INDENT_2))

def load_state(path: Path = DEFAULT_STATE_PATH) -> PersonaState:
    if not path.exists():
        return PersonaState()
    raw = orjson.loads(path.read_bytes())
    return PersonaState(**raw)  # type: ignore[arg-type]

def export_state(path: Path) -> None:
    src = DEFAULT_STATE_PATH
    if not src.exists():
        return
    path.write_bytes(src.read_bytes())

