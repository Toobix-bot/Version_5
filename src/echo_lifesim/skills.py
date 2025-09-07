from __future__ import annotations
from pathlib import Path
import orjson
from typing import Dict, List
from .models import SkillCard, PersonaState

SKILL_DIR = Path("skills")

def load_skill_cards() -> Dict[str, SkillCard]:
    cards: Dict[str, SkillCard] = {}
    if not SKILL_DIR.exists():
        return cards
    for p in SKILL_DIR.glob("*.json"):
        try:
            data = orjson.loads(p.read_bytes())
            card = SkillCard(**data)  # type: ignore[arg-type]
            cards[card.name] = card
        except Exception:
            continue
    return cards

def run_skill_tests(card: SkillCard) -> List[str]:
    results: List[str] = []
    for t in card.tests:
        # Placeholder: echo logic, pretend pass if substring in input
        ok = t.expect_sub.lower() in t.input.lower()
        status = "PASS" if ok else "FAIL"
        results.append(f"{status} {card.name}: expect '{t.expect_sub}' in '{t.input}'")
    return results

def autounlock_from_tests(state: PersonaState, cards: Dict[str, SkillCard]) -> Dict[str, List[str]]:  # pragma: no cover simple heuristic
    unlocked: List[str] = []
    failed: List[str] = []
    for card in cards.values():
        if card.name in state.unlocked_skills:
            continue
        res = run_skill_tests(card)
        if all(r.startswith("PASS") for r in res):
            if state.unlock_skill(card.name):
                unlocked.append(card.name)
        else:
            failed.append(card.name)
    return {"unlocked": unlocked, "failed": failed}