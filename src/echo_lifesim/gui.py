from __future__ import annotations
import os
import time
import sys
import streamlit as st
from pathlib import Path

# Support running via `streamlit run src/echo_lifesim/gui.py` (no package context)
try:  # pragma: no cover
    from .engine import LifeSimEngine  # type: ignore
    from .persistence import load_state, save_state, DEFAULT_STATE_PATH  # type: ignore
except ImportError:  # executed when not run as package
    # add src folder to sys.path
    src_path = Path(__file__).resolve().parents[1]  # .../src
    if str(src_path) not in sys.path:
        sys.path.insert(0, str(src_path))
    from echo_lifesim.engine import LifeSimEngine  # type: ignore
    from echo_lifesim.persistence import load_state, save_state, DEFAULT_STATE_PATH  # type: ignore

# Simple singleton engine stored in session_state

def get_engine() -> LifeSimEngine:
    if "engine" not in st.session_state:
        # try load
        if Path(DEFAULT_STATE_PATH).exists():
            try:
                st.session_state.engine = LifeSimEngine(load_state(Path(DEFAULT_STATE_PATH)))  # type: ignore
            except Exception:
                st.session_state.engine = LifeSimEngine()
        else:
            st.session_state.engine = LifeSimEngine()
    return st.session_state.engine  # type: ignore

st.set_page_config(page_title="ECHO-LifeSim", page_icon="🪞", layout="wide")

st.title("ECHO-LifeSim Preview")
engine = get_engine()

with st.sidebar:
    st.markdown("### Steuerung")
    if st.button("State speichern"):
        save_state(engine.state, Path(DEFAULT_STATE_PATH))
        st.success("Gespeichert.")
    if st.button("Neu laden"):
        try:
            engine.state = load_state(Path(DEFAULT_STATE_PATH))
            st.info("Geladen.")
        except Exception as e:
            st.error(f"Fehler: {e}")
    if st.button("Reset (Frisch)"):
        engine = LifeSimEngine()
        st.session_state.engine = engine
        st.warning("Zurückgesetzt.")
    st.markdown("### Epoch / Research")
    if st.button("Epoch +1"):
        art = engine.state.advance_epoch()
        st.success(f"Epoch {engine.state.epoch} -> Artifact: {art.title}")
    if st.button("Toggle Web Research"):
        engine.state.web_research_enabled = not engine.state.web_research_enabled
    st.caption(f"WebResearch: {'AN' if engine.state.web_research_enabled else 'AUS'}")
    if engine.state.artifacts:
        st.caption(f"Artifacts: {len(engine.state.artifacts)} (letzte: {engine.state.artifacts[-1].title})")

col_input, col_actions, col_state = st.columns([2,1,2])

with col_input:
    st.subheader("Interaktion")
    user_text = st.text_area("Eingabe", height=120, placeholder="Was beschäftigt dich gerade?")
    event_key = st.selectbox("Event (optional)", ["(kein)", *sorted(["regen","freund_absage","idee_fund"])])
    if st.button("Senden", type="primary"):
        if user_text.strip():
            result = engine.persona_reply(user_text, None if event_key == "(kein)" else event_key)
            st.session_state.last_result = result
        else:
            st.warning("Bitte Text eingeben.")
    if st.button("Vorschlag 1 ausführen"):
        res = st.session_state.get("last_result")
        if res:
            choice = res["actions"][0][0]
            engine.apply_action_result(choice)
            st.session_state.last_action = choice
    if st.button("Vorschlag 2 ausführen"):
        res = st.session_state.get("last_result")
        if res and len(res["actions"])>1:
            choice = res["actions"][1][0]
            engine.apply_action_result(choice)
            st.session_state.last_action = choice

with col_actions:
    st.subheader("Antwort & Vorschläge")
    last = st.session_state.get("last_result")
    if last:
        st.markdown(f"**Persona:** {last['reply']}")
        if last.get("reflection"):
            st.info(last["reflection"])
        st.markdown("**Aktionen**")
        for label, duration in last["actions"]:
            st.write(f"• {label} ({duration})")
        if last.get("event_effects"):
            st.caption(f"Event Effekte: {last['event_effects']}")
        if engine.state.web_research_enabled and engine.state.has_skill("web_research_3_2_1"):
            with st.expander("Web Research 3-2-1"):
                q = st.text_input("Query", key="research_q")
                if st.button("Research starten"):
                    if q.strip():
                        snippets = [
                            {"src": "synth_1", "text": f"Fakt A zu {q}"},
                            {"src": "synth_2", "text": f"Fakt B zu {q}"},
                            {"src": "synth_3", "text": f"Fakt C zu {q}"},
                        ]
                        st.write(snippets)
                    else:
                        st.warning("Query eingeben.")
    else:
        st.caption("Noch keine Interaktion.")

with col_state:
    st.subheader("Needs & Status")
    needs = engine.state.needs.model_dump()
    for k,v in needs.items():
        st.progress(int(v), text=f"{k}: {int(v)}")
    st.markdown("### Overmind")
    st.write({"thought_interval_ms": engine.state.thought_interval_ms, "streak": engine.state.success_streak})
    st.markdown("### Buffs")
    if engine.state.buffs:
        st.write(", ".join(f"{b}({ttl})" for b, ttl in engine.state.buffs.items()))
    else:
        st.caption("Keine Buffs aktiv")
    st.markdown("### Debuffs")
    if engine.state.debuffs:
        st.write(", ".join(f"{b}({ttl})" for b, ttl in engine.state.debuffs.items()))
    else:
        st.caption("Keine Debuffs aktiv")
    st.markdown("### Letzte Episoden")
    recent = engine.state.episodes[-5:]
    for ep in recent:
        st.write(f"[{ep.actor}] {ep.text}")
    st.markdown("### Thoughts")
    for th in engine.state.thoughts[-5:]:
        st.caption(f"🧠 {th.text}")

st.markdown("---")
st.caption("Preview GUI • Streamlit • Speichert automatisch nur bei Klick auf 'State speichern'")
