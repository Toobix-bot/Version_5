from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Literal, Dict
import time

TimeBlock = Literal["MORNING", "MIDDAY", "EVENING", "NIGHT"]
Location = Literal["HOME", "WORK", "OUTSIDE", "SOCIAL"]

NEED_KEYS = ["energy", "clarity", "connection", "order", "creativity", "calm"]

class Episode(BaseModel):
    ts: float = Field(default_factory=lambda: time.time())
    actor: str = "user"  # or "persona"
    text: str
    tags: List[str] = Field(default_factory=list)
    importance: float = 0.5

class NeedState(BaseModel):
    energy: int = 50
    clarity: int = 50
    connection: int = 50
    order: int = 50
    creativity: int = 50
    calm: int = 50

    def apply_delta(self, **deltas: int) -> None:
        for k, v in deltas.items():
            if k in NEED_KEYS:
                new_val = getattr(self, k) + v
                setattr(self, k, max(0, min(100, new_val)))

    def decay_towards_mid(self, amount: int = 2) -> None:
        for k in NEED_KEYS:
            val = getattr(self, k)
            if val > 50:
                setattr(self, k, max(50, val - amount))
            elif val < 50:
                setattr(self, k, min(50, val + amount))

class Preference(BaseModel):
    key: str
    weight: float = 1.0

class Note(BaseModel):
    ts: float = Field(default_factory=lambda: time.time())
    text: str

class PersonaProfile(BaseModel):
    name: str = "Ari"
    values: List[str] = ["ehrlichkeit", "lernen", "verbundenheit", "gesundheit"]
    goals: List[str] = [
        "täglich etwas dazulernen",
        "verbundenheit pflegen",
        "körperlich aktiv bleiben",
    ]
    temperament: List[str] = ["ruhig", "strukturiert", "warm"]
    voice_style: str = "kurz-konkret-warm"

class PersonaState(BaseModel):
    profile: PersonaProfile = Field(default_factory=PersonaProfile)
    needs: NeedState = Field(default_factory=NeedState)
    episodes: List["Episode"] = Field(default_factory=list)
    notes: List["Note"] = Field(default_factory=list)
    preferences: List["Preference"] = Field(default_factory=list)
    turn: int = 0
    xp: int = 0
    location: Location = "HOME"
    time_block: TimeBlock = "MORNING"
    buffs: Dict[str, int] = Field(default_factory=dict)  # name -> remaining turns
    debuffs: Dict[str, int] = Field(default_factory=dict)
    habit_counts: Dict[str, int] = Field(default_factory=dict)  # action_key -> uses

    def add_episode(self, ep: Episode) -> None:
        self.episodes.append(ep)

    def add_note(self, text: str) -> None:
        self.notes.append(Note(text=text))

    def upsert_preference(self, key: str, delta: float = 0.2) -> None:
        for pref in self.preferences:
            if pref.key == key:
                pref.weight = min(3.0, pref.weight + delta)
                return
        self.preferences.append(Preference(key=key, weight=1.0 + delta))

    def top_preferences(self, n: int = 5) -> List[str]:
        return [p.key for p in sorted(self.preferences, key=lambda p: p.weight, reverse=True)[:n]]

    def advance_time(self) -> None:
        order: List[TimeBlock] = ["MORNING", "MIDDAY", "EVENING", "NIGHT"]
        idx = order.index(self.time_block)
        self.time_block = order[(idx + 1) % len(order)]
        if self.time_block == "MORNING":
            self.needs.decay_towards_mid()
        self._tick_effects()

    def _tick_effects(self) -> None:
        def dec(d: Dict[str, int]) -> None:
            remove = []
            for k, v in d.items():
                nv = v - 1
                if nv <= 0:
                    remove.append(k)
                else:
                    d[k] = nv
            for k in remove:
                del d[k]
        dec(self.buffs)
        dec(self.debuffs)

    def record_habit(self, action_label: str) -> None:
        key = action_label.lower().strip()
        self.habit_counts[key] = self.habit_counts.get(key, 0) + 1

    def top_habits(self, n: int = 5) -> List[str]:
        return [k for k, _ in sorted(self.habit_counts.items(), key=lambda kv: kv[1], reverse=True)[:n]]
