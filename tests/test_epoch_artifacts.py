from echo_lifesim.models import PersonaState, Episode
from echo_lifesim.engine import LifeSimEngine

def test_epoch_advances_and_creates_artifact():
    state = PersonaState()
    eng = LifeSimEngine(state)
    # create some episodes
    for i in range(5):
        state.add_episode(Episode(actor="user", text=f"msg {i}"))
    art = state.advance_epoch()
    assert state.epoch == 1
    assert art in state.artifacts
    assert "Epoch 1" in art.title

def test_history_compression():
    state = PersonaState(max_episode_history=10)
    for i in range(25):
        state.add_episode(Episode(actor="user", text=f"e {i}"))
    state.advance_epoch()
    assert len(state.episodes) <= 10
