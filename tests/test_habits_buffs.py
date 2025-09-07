from echo_lifesim.engine import LifeSimEngine
from echo_lifesim.models import PersonaState

def test_habit_and_buff_application():
    eng = LifeSimEngine(PersonaState())
    # Trigger an action that grants a buff several times
    r = eng.persona_reply("Brauche Fokus und Ordnung")
    # pick an action or force one
    choice = None
    for label, _ in r["actions"]:
        if "ordnung" in label or "atem" in label:
            choice = label
            break
    if not choice:
        choice = r["actions"][0][0]
    before = eng.state.needs.clarity + eng.state.needs.order
    eng.apply_action_result(choice)
    after_first = eng.state.needs.clarity + eng.state.needs.order
    # Buff should have applied (at least minimal increase beyond delta or set buff for future)
    assert after_first >= before, "Needs should not decrease after positive action"
    # Next dummy turn to let buff passive effect run
    eng.persona_reply("weiter")
    after_second = eng.state.needs.clarity + eng.state.needs.order
    assert after_second >= after_first, "Buff passive effect should not reduce combined clarity+order"
    # Habit counter increments
    assert len(eng.state.habit_counts) >= 1
