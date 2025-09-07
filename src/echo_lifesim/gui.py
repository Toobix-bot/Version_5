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
    if st.button("State speichern", help="Speichert aktuellen Simulationszustand auf Platte"):
        save_state(engine.state, Path(DEFAULT_STATE_PATH))
        st.success("Gespeichert.")
    if st.button("Neu laden", help="Lädt zuletzt gespeicherten Zustand neu"):
        try:
            engine.state = load_state(Path(DEFAULT_STATE_PATH))
            st.info("Geladen.")
        except Exception as e:
            st.error(f"Fehler: {e}")
    if st.button("Reset (Frisch)", help="Neuer leerer Persona-State (alles wird verworfen)"):
        engine = LifeSimEngine()
        st.session_state.engine = engine
        st.warning("Zurückgesetzt.")
    st.markdown("### Epoch / Research")
    if st.button("Epoch +1", help="Forciert Epochenwechsel: ggf. Artefakt + Life-Phase-Prüfung"):
        art = engine.state.advance_epoch()
        st.success(f"Epoch {engine.state.epoch} -> Artifact: {art.title}")
    if st.button("Toggle Web Research", help="Aktiviert/Deaktiviert experimentelles Recherche-Skill Fenster"):
        engine.state.web_research_enabled = not engine.state.web_research_enabled
    st.caption(f"WebResearch: {'AN' if engine.state.web_research_enabled else 'AUS'}")
    if engine.state.artifacts:
        st.caption(f"Artifacts: {len(engine.state.artifacts)} (letzte: {engine.state.artifacts[-1].title})")
    with st.expander("Cheat Sheet (CLI)"):
        st.code("""echo-sim turn "Text" --event regen\necho-sim act "Atemfokus 2m"\necho-sim epoch\necho-sim scenario-set default\necho-sim items-load starter_pack.json\necho-sim chronicle-export chronicle.md""", language="bash")

col_input, col_actions, col_state = st.columns([2,1,2])

with col_input:
    st.subheader("Interaktion")
    # Suggested starter prompts for onboarding
    starter_prompts = [
        "Bin etwas müde aber will einen klaren nächsten Schritt",
        "Fühle mich zerstreut und brauche Fokus",
        "Bin nervös vor neuer Aufgabe – wie klein anfangen?",
        "Leicht gereizt und will runterfahren",
        "Idee im Kopf, zweifle ob sinnvoll"
    ]
    # Prefill support
    if 'user_input' not in st.session_state:
        st.session_state.user_input = ""
    cols_prompts = st.columns(len(starter_prompts))
    for i,p in enumerate(starter_prompts):
        if cols_prompts[i].button(str(i+1), help=f"Beispiel Prompt {i+1}"):
            st.session_state.user_input = p
    user_text = st.text_area("Eingabe", key="user_input", height=120, placeholder="Was beschäftigt dich gerade?", help="Kurzer Ist-Zustand + gewünschte Richtung / Frage")
    event_key = st.selectbox("Event (optional)", ["(kein)", *sorted(["regen","freund_absage","idee_fund"])])
    if st.button("Senden", type="primary", help="Eingabetext verarbeiten & Antwort generieren"):
        if user_text.strip():
            result = engine.persona_reply(user_text, None if event_key == "(kein)" else event_key)
            st.session_state.last_result = result
        else:
            st.warning("Bitte Text eingeben.")
    if st.button("Vorschlag 1 ausführen", help="Erste vorgeschlagene Mikro-Aktion anwenden"):
        res = st.session_state.get("last_result")
        if res:
            choice = res["actions"][0][0]
            engine.apply_action_result(choice)
            st.session_state.last_action = choice
    if st.button("Vorschlag 2 ausführen", help="Zweite vorgeschlagene Mikro-Aktion anwenden"):
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
    # Dynamic kontextsensitive Hinweise basierend auf Needs
    def need_hint(needs_dict):
        tips = []
        high = [k for k,v in needs_dict.items() if v >= 75]
        low = [k for k,v in needs_dict.items() if v <= 30]
        if low:
            mapping_low = {
                "energy": "Mini-Aktivierung (2m Stretch oder Atem), dann 1 fokussierter Schritt.",
                "clarity": "Externe Gedanken entladen: 3 Stichworte notieren bevor du weitermachst.",
                "connection": "Kurze Nachricht an eine Person senden (Ping ohne Erwartung).",
                "order": "60-Sek Aufräum/Sortier Sprint um Reibung zu senken.",
                "creativity": "1 verrückte Variante deiner aktuellen Idee notieren.",
                "calm": "2-Min Atem oder Spaziergang 100 Schritte langsam."}
            for k in low:
                tips.append(f"🔻 {k}: {mapping_low.get(k,'kleiner Ausgleichsschritt')}" )
        if high:
            mapping_high = {
                "energy": "Nutze das Hoch für eine anspruchsvollere Aktion (Deep Focus Block starten).",
                "clarity": "Jetzt ideal für Strukturierung / Plan verfeinern.",
                "connection": "Teile einen Fortschritt oder Dankbarkeit – verstärkt Bindung.",
                "order": "Nutze Ordnungshoch für kreativen Ausbruch (kleines Experiment).",
                "creativity": "Idee sofort in einen konkreten nächsten Task gießen.",
                "calm": "Ruhiges Fenster: diffuses Denken (Inbox leeren / Review)."}
            for k in high:
                tips.append(f"🔺 {k}: {mapping_high.get(k,'gezielt einsetzen für Fortschritt')}" )
        # Balance Check
        spread = max(needs_dict.values()) - min(needs_dict.values())
        if spread > 40:
            tips.append("⚖️ Große Streuung: 1 Ausgleich vor weiterer Verstärkung")
        return tips[:4]
    hints = need_hint(needs)
    if hints:
        with st.expander("Kontext Hinweise", expanded=True if len(engine.state.episodes)<5 else False):
            for h in hints:
                st.caption(h)
    st.markdown("### Overmind")
    st.write({"thought_interval_ms": engine.state.thought_interval_ms, "streak": engine.state.success_streak})
    st.markdown("### Phase & Stats")
    st.write({
        "life_phase": engine.state.life_phase,
        "discipline": engine.state.stat_discipline,
        "insight": engine.state.stat_insight,
        "resilience": engine.state.stat_resilience,
    })
    if engine.state.achievements_unlocked:
        st.caption("Achievements: " + ", ".join(engine.state.achievements_unlocked))
    if engine.state.skill_mastery:
        st.caption("Mastery: " + ", ".join(f"{k}:{v}" for k,v in engine.state.skill_mastery.items()))
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
    topics = engine.state.topics
    tab_objs = st.tabs(topics)
    for t_idx, t in enumerate(topics):
        with tab_objs[t_idx]:
            filtered = [ep for ep in reversed(engine.state.episodes) if ep.topic_id == t][:10]
            for ep in filtered:
                st.write(f"[{ep.actor}] {ep.text}")
    st.markdown("### Thoughts")
    for th in engine.state.thoughts[-5:]:
        st.caption(f"🧠 {th.text}")
    if st.button("Chronicle Export anzeigen", help="Zeigt Vorschau der Markdown Lebenschronik"):
        st.code(engine.build_chronicle()[:4000])

# Onboarding / Hilfe Bereich unten, nur wenn wenige Episoden
if len(engine.state.episodes) < 3:
    with st.expander("🆕 Erste Schritte / Hilfe", expanded=True):
        st.markdown("""
**Willkommen!** Kurzer Leitfaden:
1. Beschreibe deinen inneren Zustand oder ein kleines Ziel.
2. Klicke 'Senden'. Lies die Antwort + zwei Aktionsvorschläge.
3. Führe genau eine Mikro-Aktion aus (Knopf). Beobachte Needs.
4. Wiederhole 2–3x, dann teste einen *Epoch +1* (Sidebar) für Artefakt.
5. Später: `Scenario` wechseln (CLI) oder Items laden.
        """)
        st.caption("Tipp: Halte Eingaben kurz (1–2 Sätze). Fokus auf *wie es sich anfühlt* + gewünschte Richtung.")
        # Tutorial Ausschnitt anzeigen
        from pathlib import Path as _P
        tut_path = _P(__file__).resolve().parents[2] / "README_TUTORIAL.md"
        snippet = ""
        try:
            raw = tut_path.read_text(encoding="utf-8")
            snippet = raw.split("## 3. Wichtige Konzepte")[0][:1000]
        except Exception:
            snippet = "(Tutorial Datei nicht gefunden)"
        with st.expander("Tutorial Vorschau (README_TUTORIAL.md)"):
            st.code(snippet)
else:
    with st.expander("Hilfe / Tips"):
        st.write("Nutze die Zahlen-Buttons für schnelle Beispiel-Prompts. Epoch Wechsel erzeugt ggf. Artefakt & Life-Phase. CLI 'echo-sim help-start' für Leitfaden.")

st.markdown("---")
st.caption("Preview GUI • Streamlit • Speichert automatisch nur bei Klick auf 'State speichern'")
