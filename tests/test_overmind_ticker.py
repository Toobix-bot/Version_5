from echo_lifesim.engine import LifeSimEngine
from echo_lifesim.models import PersonaState
import time

def test_overmind_adjusts_on_needs():
    state = PersonaState()
    state.needs.clarity = 35  # low clarity should speed ticker
    eng = LifeSimEngine(state)
    before = eng.state.thought_interval_ms
    eng.persona_reply("bin etwas vernebelt")
    after = eng.state.thought_interval_ms
    assert after <= before, "Ticker interval should not increase when clarity low"

def test_suggestion_length_scales_with_streak():
    eng = LifeSimEngine(PersonaState())
    # simulate acceptance streak
    for i in range(4):
        r = eng.persona_reply(f"turn {i}")
        # accept first action each time
        eng.apply_action_result(r['actions'][0][0])
    # after streak >3 we expect suggestion len to be raised (overmind run on persona_reply)
    r2 = eng.persona_reply("weiter")
    assert 3 <= len(r2['actions']) <= 4

def test_ticker_generates_thoughts():
    state = PersonaState()
    state.thought_interval_ms = 10  # very fast
    eng = LifeSimEngine(state)
    eng.persona_reply("eins")
    time.sleep(0.02)
    eng.persona_reply("zwei")
    assert len(eng.state.thoughts) >= 1