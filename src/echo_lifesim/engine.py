from __future__ import annotations
from typing import Tuple, List, Dict, TypedDict, Optional
import random
from .models import PersonaState, Episode
from .llm_client import get_groq
from .memory import MemoryIndex

EVENT_EFFECTS = {
    "regen": {"calm": +5, "creativity": +3},
    "freund_absage": {"connection": -6, "calm": -4},
    "idee_fund": {"creativity": +8, "clarity": +4},
}

BUFF_LIBRARY: Dict[str, Dict[str, int]] = {
    "klarer_kopf": {"clarity": +2},
    "ordnung_plus": {"order": +2},
}
DEBUFF_LIBRARY: Dict[str, Dict[str, int]] = {
    "überreizt": {"creativity": -2, "calm": -2},
}

class PersonaReply(TypedDict):
    reply: str
    actions: List[Tuple[str, str]]
    reflection: Optional[str]
    event_effects: Dict[str, int]
    needs: Dict[str, int]


class LifeSimEngine:
    def __init__(self, state: PersonaState | None = None):
        self.state = state or PersonaState()
        self.memory = MemoryIndex(self.state)

    def ingest_user_input(self, text: str) -> None:
        self.state.add_episode(Episode(actor="user", text=text, tags=[]))
        # lightweight preference mining
        for token in ["morgens", "abends", "ruhig", "fokus"]:
            if token in text.lower():
                self.state.upsert_preference(token)

    def apply_event(self, event_key: Optional[str]) -> Dict[str, int]:
        if not event_key:
            return {}
        effects = EVENT_EFFECTS.get(event_key, {})
        self.state.needs.apply_delta(**effects)
        return effects

    def suggest_actions(self) -> List[Tuple[str, str]]:
        # returns list of (label, duration_tag)
        candidates: List[Tuple[str, str]] = []
        needs = self.state.needs
        if needs.energy < 45:
            candidates.append(("2-Min atemfokus", "2-Min"))
        if needs.order < 45:
            candidates.append(("10-Min ordnungsecke", "10-Min"))
        if needs.connection < 45:
            candidates.append(("nachricht an freund", "2-Min"))
        if needs.creativity < 45:
            candidates.append(("skizze 2 ideen", "5-Min"))
        if not candidates:
            candidates = [
                ("kurzer stretch", "2-Min"),
                ("mini lernnotiz", "5-Min"),
                ("ordner sortieren", "10-Min"),
            ]
        random.shuffle(candidates)
        # pick top two unique by label length variety
        base = candidates[:2]
        # habit bias: if a habit is strong, ensure at least one appears occasionally
        top_habits = self.state.top_habits(3)
        for h in top_habits:
            for c in candidates:
                if h.startswith(c[0][:5]) and c not in base:
                    base.append(c)
                    break
        return base[:2]

    def persona_reply(self, user_text: str, event_key: Optional[str] = None) -> PersonaReply:
        self.state.turn += 1
        self.ingest_user_input(user_text)
        event_effects = self.apply_event(event_key)
        retrieved = self.memory.retrieve(user_text, k=3)
        # basic reflection every 5 turns
        reflection = None
        if self.state.turn % 5 == 0:
            pref_str = ", ".join(self.state.top_preferences(3)) or "(noch keine)"
            reflection = f"Reflexion: Ich achte auf {pref_str}. Bedürfnisse balanciere ich aktiv."
            self.state.add_note(reflection)
        actions = self.suggest_actions()
        reply = self._compose_reply(user_text, retrieved, actions, event_effects)
        # Optional LLM enrichment if key present
        groq = get_groq()
        if groq.available():
            system = "Du bist Ari, kurz, konkret, warm. Max 3 Sätze. Nutze Vorschläge nicht wörtlich wieder, sondern baue sie sinnvoll ein."
            enriched = groq.chat(system, f"User: {user_text}\nKontext: {reply}")
            if enriched:
                reply = enriched[:320]
        self.state.add_episode(Episode(actor="persona", text=reply))
        return {
            "reply": reply,
            "actions": actions,
            "reflection": reflection,
            "event_effects": event_effects,
            "needs": self.state.needs.model_dump(),
        }

    def _compose_reply(self, user_text: str, retrieved: List[Episode], actions: List[Tuple[str, str]], effects: Dict[str, int]) -> str:
        # simple heuristics for tone
        needs = self.state.needs
        mood_bits: List[str] = []
        if needs.energy < 40:
            mood_bits.append("etwas niedrige Energie")
        if needs.connection < 40:
            mood_bits.append("leicht isoliert")
        mood = ", ".join(mood_bits) if mood_bits else "stabile Balance"
        action_str = " / ".join(f"{a} ({d})" for a, d in actions)
        ref_piece = " | ".join(ep.text for ep in retrieved[:2])
        return f"Ich spüre {mood}. Vorschläge: {action_str}. Kontext: {ref_piece[:140]}"  # limit length

    def apply_action_result(self, choice_label: str | None) -> None:
        if not choice_label:
            return
        # simplistic XP & need adjustments
        self.state.xp += 1
        self.state.record_habit(choice_label)
        if "atem" in choice_label:
            self.state.needs.apply_delta(calm=+5, clarity=+3)
            self.state.buffs.setdefault("klarer_kopf", 3)
        elif "ordnung" in choice_label:
            self.state.needs.apply_delta(order=+7, calm=+2)
            self.state.buffs.setdefault("ordnung_plus", 3)
        elif "freund" in choice_label:
            self.state.needs.apply_delta(connection=+8)
        elif "stretch" in choice_label:
            self.state.needs.apply_delta(energy=+4, creativity=+2)
        self.state.advance_time()
        self._apply_status_effects()

    def _apply_status_effects(self) -> None:
        # passive per-turn buff/debuff adjustments
        for b, _ in list(self.state.buffs.items()):
            eff = BUFF_LIBRARY.get(b)
            if eff:
                self.state.needs.apply_delta(**eff)
        for d, _ in list(self.state.debuffs.items()):
            eff = DEBUFF_LIBRARY.get(d)
            if eff:
                self.state.needs.apply_delta(**eff)
