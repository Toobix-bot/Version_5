from __future__ import annotations
from typing import Tuple, List, Dict, TypedDict, Optional, Any
import random
import time
from .models import PersonaState, Episode
from .catalogs import load_actions, load_events
from .llm_client import get_groq
from .memory import MemoryIndex

EVENT_CACHE = load_events()

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
        topic = "main"
        lowered = text.lower()
        if any(k in lowered for k in ["arbeit","job","projekt"]):
            topic = "work"
        elif any(k in lowered for k in ["freund","sozial","famil"]):
            topic = "social"
        elif any(k in lowered for k in ["gesund","körper","sport"]):
            topic = "health"
        self.state.add_episode(Episode(actor="user", text=text, tags=[], topic_id=topic))
        for token in ["morgens", "abends", "ruhig", "fokus"]:
            if token in text.lower():
                self.state.upsert_preference(token)

    def apply_event(self, event_key: Optional[str]) -> Dict[str, int]:
        if not event_key:
            return {}
        spec = EVENT_CACHE.get(event_key)
        if not spec:
            return {}
        effects = spec.get("need_effects", {})
        if effects:
            self.state.needs.apply_delta(**effects)
        return effects

    def maybe_trigger_biased_event(self) -> Optional[Dict[str, Any]]:
        """Trigger an event influenced by scenario event_bias if any.
        Picks from events where name appears in scenario bias list with weighted random.
        """
        scen_name = self.state.world.scenario
        from .world_assets import load_scenario
        try:
            scen = load_scenario(f"{scen_name}.json")
        except Exception:
            return None
        bias = scen.get("event_bias", {})
        if not bias:
            return None
        # Build weighted list
        weighted: List[str] = []
        # Build from bias keys directly (assumed valid event keys)
        for ev_name, weight in bias.items():
            weighted.extend([ev_name] * max(1, int(weight)))
        if not weighted:
            return None
        import random
        if random.random() < 0.25:  # 25% chance per tick
            chosen = random.choice(weighted)
            eff = self.apply_event(chosen)
            return {"applied": chosen, "effects": eff}
        return None

    def suggest_actions(self) -> List[Tuple[str, str]]:
        s = self.state
        candidates: List[Tuple[str, str]] = []
        # dynamic action catalog weighting
        catalog = load_actions()
        n = s.needs
        scored: List[Tuple[float, Tuple[str, str], Dict[str, int]]] = []
        for a in catalog:
            label = a.get("label", "")
            duration = a.get("duration", "?")
            effects: Dict[str, int] = a.get("need_effects", {})
            # score: sum of positive deltas for currently low needs + base weight
            weight = float(a.get("weight", 1.0))
            score = weight
            for need, delta in effects.items():
                val = getattr(n, need, 50)
                if delta > 0 and val < 55:
                    score += (55 - val) * (delta / 10)
            scored.append((score, (label, duration), effects))
        if not scored:  # fallback safety
            scored = [(1.0, ("kurzer stretch", "2-Min"), {})]
        scored.sort(key=lambda x: x[0], reverse=True)
        candidates = [tpl for _, tpl, _ in scored[:12]]  # keep top pool before variety rules
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
        # persona reply inherits last user topic (if any)
        last_user = next((ep for ep in reversed(self.state.episodes) if ep.actor == "user"), None)
        topic = last_user.topic_id if last_user else "main"
        self.state.add_episode(Episode(actor="persona", text=reply, topic_id=topic))
        adjustments = self.overmind_step()
        # log adjustments as system episode for transparency
        if adjustments:
            self.state.add_episode(Episode(actor="system", text=f"overmind {adjustments}", tags=["overmind"], topic_id=topic))
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
        # skill mastery tracking (simple mapping by label prefixes)
        if "web research" in choice_label.lower():
            key = "web_research_3_2_1"
            self.state.skill_uses[key] = self.state.skill_uses.get(key, 0) + 1
            uses = self.state.skill_uses[key]
            # mastery levels every 5 uses up to 5
            new_level = min(5, uses // 5)
            if new_level > self.state.skill_mastery.get(key, 0):
                self.state.skill_mastery[key] = new_level
                self.state.add_episode(Episode(actor="system", text=f"skill_mastery_up {key} {new_level}", tags=["skill"], topic_id="main"))
        # artifact auto awarding every 25 xp
        if self.state.xp % 25 == 0:
            self.state.add_artifact(title=f"Milestone XP {self.state.xp}", effect="milestone", notes="Auto-award")
        # derive effects from catalog for consistency
        catalog_map = {a.get("label"): a for a in load_actions()}
        spec = catalog_map.get(choice_label)
        applied: Dict[str, int] = {}
        if spec:
            eff = spec.get("need_effects", {})
            if eff:
                self.state.needs.apply_delta(**eff)
                applied = eff
                # simple buff inference
                if "clarity" in eff and eff["clarity"] >= 3:
                    self.state.buffs.setdefault("klarer_kopf", 3)
                if "order" in eff and eff["order"] >= 6:
                    self.state.buffs.setdefault("ordnung_plus", 3)
        self.state.advance_time()
        self._apply_status_effects()
        if applied:
            self.state.add_episode(Episode(actor="system", text=f"action_effect {choice_label} {applied}", tags=["action_effect"], topic_id="main"))
        # objective tracking: mark need_raise done if threshold reached
        if self.state.daily_objectives:
            for obj in self.state.daily_objectives:
                if not obj.get("done") and obj.get("type") == "need_raise":
                    need = str(obj.get("need"))
                    target = int(obj.get("target", 0))
                    val = getattr(self.state.needs, need, 0)  # type: ignore[arg-type]
                    if isinstance(val, (int, float)) and val >= target:
                        obj["done"] = True
                        self.state.add_episode(Episode(actor="system", text=f"objective_done {obj['id']}", tags=["objective"], topic_id="main"))

    # life chronicle (basic)
    def build_chronicle(self) -> str:
        s = self.state
        lines: List[str] = []
        lines.append(f"Life Chronicle – Epoch {s.epoch} | XP {s.xp}")
        lines.append(f"Day: {s.day_counter}")
        lines.append(f"Life Phase: {s.life_phase}  (History: {'>'.join(s.life_phase_history)})")
        lines.append(f"Stats: discipline={s.stat_discipline} insight={s.stat_insight} resilience={s.stat_resilience}")
        lines.append(f"Top Preferences: {', '.join(s.top_preferences(5)) or '-'}")
        lines.append(f"Top Habits: {', '.join(s.top_habits(5)) or '-'}")
        lines.append(f"Artifacts: {len(s.artifacts)}")
        if s.achievements_unlocked:
            lines.append("Achievements: " + ", ".join(s.achievements_unlocked))
        lines.append("Topics: " + ", ".join(s.topics))
        if s.daily_objectives:
            active = [f"{o['id']}:{'done' if o.get('done') else o.get('target')}" for o in s.daily_objectives]
            lines.append("Objectives: " + ", ".join(active))
        lines.append("-- Milestones --")
        for art in s.artifacts:
            lines.append(f"Epoch {art.epoch}: {art.title} :: {art.notes}")
        lines.append("-- Recent Episodes --")
        for ep in s.episodes[-30:]:
            lines.append(f"[{ep.actor}|{ep.topic_id}] {ep.text}")
        return "\n".join(lines)

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

    # autonomous background tick (simplified)
    def autonomous_tick(self) -> Dict[str, Any]:  # pragma: no cover basic heuristic
        s = self.state
        result: Dict[str, Any] = {"generated": []}
        # produce a spontaneous thought if enough time
        self._maybe_tick_thoughts()
        # minor world tick
        s.world.tick += 1
        # scan achievements
        self._scan_achievements()
        # if night & not yet dreamed -> dream
        if s.time_block == "NIGHT" and not s.dream_night_flag:
            dream = self._generate_dream()
            if dream:
                result["generated"].append("dream")
        # biased event chance
        biased = self.maybe_trigger_biased_event()
        if biased:
            result["biased_event"] = biased.get("applied")
        return result

    def _scan_achievements(self) -> None:
        s = self.state
        # simple conditions
        conditions = {
            "streak_5": lambda: s.success_streak >= 5,
            "xp_50": lambda: s.xp >= 50,
            "clarity_70": lambda: s.needs.clarity >= 70,
            "artifact_3": lambda: len(s.artifacts) >= 3,
        }
        for key, fn in conditions.items():
            if key not in s.achievements_unlocked and fn():
                s.achievements_unlocked.append(key)
                s.add_episode(Episode(actor="system", text=f"achievement_unlocked {key}", tags=["achievement"], topic_id="main"))
        # derive stats roughly
        s.stat_discipline = max(s.stat_discipline, s.success_streak)
        s.stat_insight = max(s.stat_insight, len([t for t in s.thoughts if 'Fokus' in t.text]))
        s.stat_resilience = max(s.stat_resilience, s.rejected_actions)

    def _generate_dream(self) -> Optional[str]:
        s = self.state
        # summarize last few episodes into a dream thought
        recent = [ep.text for ep in reversed(s.episodes) if ep.actor == "user"][:5]
        if not recent:
            return None
        dream_txt = "Traum: " + " | ".join(r[:30] for r in recent)[-240:]
        s.maybe_add_thought(dream_txt, refs={"type": ["dream"]})
        s.dream_night_flag = True
        # small chance to create insight artifact
        if random.random() < 0.25:
            art = s.add_artifact(title="Insight Fragment", effect="insight", notes="dream synthesis")
            s.add_episode(Episode(actor="system", text=f"dream_artifact {art.title}", tags=["dream"], topic_id="main"))
        return dream_txt
