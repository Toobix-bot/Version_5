from __future__ import annotations
from typing import Tuple, List, Dict, TypedDict, Optional
import random
import time
from .models import PersonaState, Episode
from .llm_client import get_groq
from .memory import MemoryIndex

EVENT_EFFECTS: Dict[str, Dict[str, int]] = {
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
    overmind: Dict[str, int | str]


class LifeSimEngine:
    def __init__(self, state: PersonaState | None = None):
        self.state = state or PersonaState()
        self.memory = MemoryIndex(self.state)
        self._last_tick_check = time.time()

    def ingest_user_input(self, text: str) -> None:
        self.state.add_episode(Episode(actor="user", text=text, tags=[]))
        for token in ["morgens", "abends", "ruhig", "fokus"]:
            if token in text.lower():
                self.state.upsert_preference(token)

    def apply_event(self, event_key: Optional[str]) -> Dict[str, int]:
        if not event_key:
            return {}
        effects = EVENT_EFFECTS.get(event_key, {})
        if effects:
            self.state.needs.apply_delta(**effects)
        return effects

    def suggest_actions(self) -> List[Tuple[str, str]]:
        s = self.state
        candidates: List[Tuple[str, str]] = []
        n = s.needs
        # base candidate generation
        if n.energy < 45:
            candidates.append(("2-Min atemfokus", "2-Min"))
        if n.order < 45:
            candidates.append(("10-Min ordnungsecke", "10-Min"))
        if n.connection < 45:
            candidates.append(("nachricht an freund", "2-Min"))
        if n.creativity < 45:
            candidates.append(("skizze 2 ideen", "5-Min"))
        if not candidates:
            candidates = [
                ("kurzer stretch", "2-Min"),
                ("mini lernnotiz", "5-Min"),
                ("ordner sortieren", "10-Min"),
                ("tiefer fokus block", "15-Min"),
            ]
        # intensity filter / reorder
        if s.om_intensity == 1:
            candidates = [c for c in candidates if not c[1].startswith("15")]
        elif s.om_intensity == 3:
            # ensure at least one higher effort at front
            for c in candidates:
                if c[1].startswith("15"):
                    candidates.remove(c)
                    candidates.insert(0, c)
                    break
        # variety handling
        random.shuffle(candidates)
        if s.om_variety == 1:
            # reinforce habits: push most frequent habit-like candidate up
            for h in s.top_habits(3):
                for c in candidates:
                    if h.startswith(c[0][:5]):
                        candidates.remove(c)
                        candidates.insert(0, c)
                        break
                break
        elif s.om_variety == 3:
            # inject random novel suggestion rarely
            novel_pool = [
                ("5-Min journal stichpunkte", "5-Min"),
                ("kurzer dankbarkeits-check", "2-Min"),
            ]
            if random.random() < 0.5:
                candidates.insert(0, random.choice(novel_pool))
        # finalize length
        limit = max(1, min(4, s.om_suggestion_len))
        trimmed = candidates[:limit]
        # skill-based injection: web research
        if s.web_research_enabled and s.has_skill("web_research_3_2_1"):
            # put a lightweight research action if not already there
            label = "3-2-1 web research mini"
            if all(label not in c[0] for c in trimmed):
                trimmed.append((label, "5-Min"))
        return trimmed

    def persona_reply(self, user_text: str, event_key: Optional[str] = None) -> PersonaReply:
        self.state.turn += 1
        self.ingest_user_input(user_text)
        event_effects = self.apply_event(event_key)
        retrieved = self.memory.retrieve(user_text, k=3)
        self._maybe_tick_thoughts()
        reflection: Optional[str] = None
        if self.state.turn % 5 == 0:
            pref_str = ", ".join(self.state.top_preferences(3)) or "(noch keine)"
            reflection = f"Reflexion: Ich achte auf {pref_str}. Bedürfnisse balanciere ich aktiv."
            self.state.add_note(reflection)
        actions = self.suggest_actions()
        reply = self._compose_reply(user_text, retrieved, actions, event_effects)
        groq = get_groq()
        if groq.available():
            system = "Du bist Ari, kurz, konkret, warm. Max 3 Sätze. Nutze Vorschläge nicht wörtlich wieder, sondern baue sie sinnvoll ein."
            enriched = groq.chat(system, f"User: {user_text}\nKontext: {reply}")
            if enriched:
                reply = enriched[:320]
        self.state.add_episode(Episode(actor="persona", text=reply))
        adjustments = self.overmind_step()
        # log adjustments as system episode for transparency
        if adjustments:
            self.state.add_episode(Episode(actor="system", text=f"overmind {adjustments}", tags=["overmind"]))
        return {
            "reply": reply,
            "actions": actions,
            "reflection": reflection,
            "event_effects": event_effects,
            "needs": self.state.needs.model_dump(),
            "overmind": adjustments,
        }

    def _compose_reply(self, user_text: str, retrieved: List[Episode], actions: List[Tuple[str, str]], effects: Dict[str, int]) -> str:
        n = self.state.needs
        mood_bits: List[str] = []
        if n.energy < 40:
            mood_bits.append("etwas niedrige Energie")
        if n.connection < 40:
            mood_bits.append("leicht isoliert")
        mood = ", ".join(mood_bits) if mood_bits else "stabile Balance"
        action_str = " / ".join(f"{a} ({d})" for a, d in actions)
        ref_piece = " | ".join(ep.text for ep in retrieved[:2])
        return f"Ich spüre {mood}. Vorschläge: {action_str}. Kontext: {ref_piece[:140]}"

    def apply_action_result(self, choice_label: str | None) -> None:
        if not choice_label:
            return
        self.state.xp += 1
        self.state.accepted_actions += 1
        self.state.success_streak += 1
        self.state.record_habit(choice_label)
        # artifact auto awarding every 25 xp
        if self.state.xp % 25 == 0:
            self.state.add_artifact(title=f"Milestone XP {self.state.xp}", effect="milestone", notes="Auto-award")
        cl = choice_label.lower()
        if "atem" in cl:
            self.state.needs.apply_delta(calm=+5, clarity=+3)
            self.state.buffs.setdefault("klarer_kopf", 3)
        elif "ordnung" in cl:
            self.state.needs.apply_delta(order=+7, calm=+2)
            self.state.buffs.setdefault("ordnung_plus", 3)
        elif "freund" in cl:
            self.state.needs.apply_delta(connection=+8)
        elif "stretch" in cl:
            self.state.needs.apply_delta(energy=+4, creativity=+2)
        self.state.advance_time()
        self._apply_status_effects()

    def reject_action(self) -> None:
        self.state.rejected_actions += 1
        self.state.success_streak = 0

    def _apply_status_effects(self) -> None:
        for b, _ in list(self.state.buffs.items()):
            eff = BUFF_LIBRARY.get(b)
            if eff:
                self.state.needs.apply_delta(**eff)
        for d, _ in list(self.state.debuffs.items()):
            eff = DEBUFF_LIBRARY.get(d)
            if eff:
                self.state.needs.apply_delta(**eff)

    def _maybe_tick_thoughts(self) -> None:
        s = self.state
        if not s.thought_active or s.thought_mute:
            return
        now = time.time()
        if (now - s.last_thought_ts) * 1000 < s.thought_interval_ms:
            return
        recent = [ep for ep in reversed(s.episodes) if ep.actor == "user"][:2]
        if recent:
            summary_bits = [ep.text[:40] for ep in recent]
            raw_thought = f"Fokus: {' | '.join(summary_bits)}"
            thought = raw_thought[: self.state.thought_max_len]
            s.maybe_add_thought(thought)
            s.last_thought_ts = now

    def overmind_step(self) -> Dict[str, int | str]:
        s = self.state
        adjustments: Dict[str, int | str] = {}
        # clarity drives ticker speed
        if s.needs.clarity < 40:
            s.thought_interval_ms = max(4000, s.thought_interval_ms - 500)
        else:
            if s.thought_interval_ms < 8000:
                s.thought_interval_ms += 250
        adjustments["thought_interval_ms"] = s.thought_interval_ms
        # energy influences intensity
        if s.needs.energy < 40:
            s.om_intensity = 1
        elif s.needs.energy > 65 and s.needs.clarity > 55:
            s.om_intensity = 3
        else:
            s.om_intensity = 2
        adjustments["om_intensity"] = s.om_intensity
        # connection influences variety
        if s.needs.connection < 40:
            s.om_variety = 1
        elif s.needs.connection > 60:
            s.om_variety = 3
        else:
            s.om_variety = 2
        adjustments["om_variety"] = s.om_variety
        # success streak modulates suggestion length (1-4)
        streak = s.success_streak
        if streak <= 1:
            s.om_suggestion_len = 2
        elif streak <= 3:
            s.om_suggestion_len = 3
        else:
            s.om_suggestion_len = 4
        adjustments["om_suggestion_len"] = s.om_suggestion_len
        return adjustments
