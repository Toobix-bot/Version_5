from echo_lifesim.engine import LifeSimEngine
from echo_lifesim.models import PersonaState

def test_turn_and_action():
    eng = LifeSimEngine(PersonaState())
    r = eng.persona_reply("Ich bin müde und unruhig")
    assert r["actions"], "Should propose at least one action"
    first = r["actions"][0][0]
    eng.apply_action_result(first)
    assert eng.state.turn == 1

def test_reflection_every_five():
    eng = LifeSimEngine()
    ref = None
    for i in range(5):
        r = eng.persona_reply(f"Input {i}")
        ref = r["reflection"]
    assert ref is not None
