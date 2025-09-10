from __future__ import annotations
from pydantic import BaseModel, Field
from typing import List, Literal, Dict, Any
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
    topic_id: str = "main"

class Thought(BaseModel):
    ts: float = Field(default_factory=lambda: time.time())
    text: str
    source: str = "ticker"  # future: overmind, system, reflection
    refs: Dict[str, List[int] | List[str]] = Field(default_factory=dict)

class WorldEntity(BaseModel):
    id: str
    kind: str = "PLACE"  # PLACE | PERSON | GROUP
    name: str
    attrs: Dict[str, Any] = Field(default_factory=dict)

class WorldState(BaseModel):
    scenario: str = "default"
    tick: int = 0
    entities: List[WorldEntity] = Field(default_factory=list)
    def add_entity(self, ent: WorldEntity) -> None:
        self.entities.append(ent)

class SkillTest(BaseModel):
    input: str
    expect_sub: str

class SkillCard(BaseModel):
    name: str
    purpose: str = ""
    io_in: str = "text"
    io_out: str = "text"
    limits: Dict[str, int] = Field(default_factory=dict)
    examples: List[str] = Field(default_factory=list)
    tests: List[SkillTest] = Field(default_factory=list)
    enabled: bool = True

class Artifact(BaseModel):
    epoch: int
    title: str
    effect: str = "flavor"
    notes: str = ""

class Item(BaseModel):
    name: str
    effect_buffs: Dict[str, int] = Field(default_factory=dict)  # buff -> turns each morning
    passive_need_delta: Dict[str, int] = Field(default_factory=dict)  # applied each MORNING
    notes: str = ""

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
    # counters & meta
    accepted_actions: int = 0
    rejected_actions: int = 0
    success_streak: int = 0
    epoch: int = 0
    # thought ticker
    thoughts: List[Thought] = Field(default_factory=list)
    thought_active: bool = True
    thought_mute: bool = False
    thought_interval_ms: int = 8000
    last_thought_ts: float = Field(default_factory=lambda: 0.0)
    thought_max_len: int = 140
    # overmind adaptive knobs
    om_suggestion_len: int = 2  # how many action suggestions to surface
    om_variety: int = 1          # 1=low (habit bias strong), 2=med, 3=high randomness
    om_intensity: int = 1        # 1=light actions, 2=mixed, 3=push higher effort
    # skills & artifacts
    unlocked_skills: List[str] = Field(default_factory=list)
    artifacts: List[Artifact] = Field(default_factory=list)
    topics: List[str] = Field(default_factory=lambda: ["main"])  # known topic ids
    # world & meta
    world: WorldState = Field(default_factory=WorldState)
    # achievements & stats
    achievements_unlocked: List[str] = Field(default_factory=list)
    stat_discipline: int = 0
    stat_insight: int = 0
    stat_resilience: int = 0
    dream_night_flag: bool = False  # to avoid multiple dream generations per night
    # items & mastery & phases
    items: List[Item] = Field(default_factory=list)
    skill_uses: Dict[str, int] = Field(default_factory=dict)  # raw use counters
    skill_mastery: Dict[str, int] = Field(default_factory=dict)  # level per skill
    life_phase: str = "phase_1"  # phase_1 -> phase_4
    life_phase_history: List[str] = Field(default_factory=lambda: ["phase_1"])
    # feature flags
    web_research_enabled: bool = False
    # history management
    max_episode_history: int = 400
    # progression / objectives
    day_counter: int = 0
    daily_objectives: List[Dict[str, Any]] = Field(default_factory=list)
    last_objective_day: int = -1

    def add_episode(self, ep: Episode) -> None:
        if ep.topic_id not in self.topics:
            self.topics.append(ep.topic_id)
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
            # new day
            self.day_counter += 1
            self.needs.decay_towards_mid()
            self.dream_night_flag = False  # reset dream flag at new day
            self._apply_item_passives()
            self._maybe_generate_objectives()
        self._tick_effects()

    def _maybe_generate_objectives(self) -> None:
        if self.last_objective_day == self.day_counter:
            return
        # simple: select up to 2 lowest needs and create raise objectives
        need_vals = {k: getattr(self.needs, k) for k in NEED_KEYS}
        lows = sorted(need_vals.items(), key=lambda x: x[1])[:2]
        self.daily_objectives = []
        for name, val in lows:
            target = min(100, val + 8)
            self.daily_objectives.append({
                "id": f"need_{name}",
                "type": "need_raise",
                "need": name,
                "baseline": val,
                "target": target,
                "done": False,
            })
        self.last_objective_day = self.day_counter
        if self.daily_objectives:
            self.add_episode(Episode(actor="system", text=f"objectives_new {[o['id'] for o in self.daily_objectives]}", tags=["objective"], topic_id="main"))

    def _tick_effects(self) -> None:
        def dec(d: Dict[str, int]) -> None:
            remove: List[str] = []
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

    # thought handling
    def maybe_add_thought(self, text: str, refs: Dict[str, List[int] | List[str]] | None = None) -> None:
        if self.thought_mute:
            return
        # enforce max len
        truncated = text[: self.thought_max_len]
        self.thoughts.append(Thought(text=truncated, refs=refs or {}))

    # skills
    def unlock_skill(self, name: str) -> bool:
        if name in self.unlocked_skills:
            return False
        self.unlocked_skills.append(name)
        return True

    def has_skill(self, name: str) -> bool:
        return name in self.unlocked_skills

    # artifacts
    def add_artifact(self, title: str, effect: str = "flavor", notes: str = "") -> Artifact:
        art = Artifact(epoch=self.epoch, title=title, effect=effect, notes=notes)
        self.artifacts.append(art)
        return art

    # epoch & compression
    def advance_epoch(self) -> Artifact:
        """Advance epoch: create summary artifact & compress old episodes."""
        self.epoch += 1
        # build summary
        top_prefs = ",".join(self.top_preferences(3)) or "-"
        top_habits = ",".join(self.top_habits(3)) or "-"
        summary = f"E{self.epoch}: prefs={top_prefs} habits={top_habits} episodes={len(self.episodes)}"
        art = self.add_artifact(title=f"Epoch {self.epoch} Summary", effect="summary", notes=summary)
        # compress episodes if exceeding cap (keep newest N)
        if len(self.episodes) > self.max_episode_history:
            self.episodes = self.episodes[-self.max_episode_history:]
        self._maybe_advance_life_phase()
        return art

    def _apply_item_passives(self) -> None:
        for it in self.items:
            if it.passive_need_delta:
                self.needs.apply_delta(**it.passive_need_delta)
            for buff, turns in it.effect_buffs.items():
                # refresh buff with max remaining if already present
                cur = self.buffs.get(buff, 0)
                self.buffs[buff] = max(cur, turns)

    def _maybe_advance_life_phase(self) -> None:
        # simple thresholds by epoch or xp
        mapping = [
            ("phase_2", lambda: self.epoch >= 2 or self.xp >= 40),
            ("phase_3", lambda: self.epoch >= 4 or self.xp >= 120),
            ("phase_4", lambda: self.epoch >= 6 or self.xp >= 250),
        ]
        for phase, cond in mapping:
            if phase not in self.life_phase_history and cond():
                self.life_phase = phase
                self.life_phase_history.append(phase)
                self.add_note(f"LifePhase erreicht: {phase}")
                break

# rebuild to resolve forward refs
PersonaState.model_rebuild()
