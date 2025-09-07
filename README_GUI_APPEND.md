## Schnelle GUI Vorschau (Streamlit)

Falls Patch im Haupt-README fehlschlug, hier der Abschnitt zum manuellen Einfügen.

Installation (Extra):
```bash
pip install .[gui]
```
Oder:
```bash
pip install streamlit>=1.36.0
```

Start:
```bash
streamlit run src/echo_lifesim/gui.py
```

Enthalten:
- Eingabetext + Event Auswahl
- Persona Antwort + Reflexion (alle 5 Züge)
- Zwei Aktions-Buttons
- Needs (Progress Bars)
- Buffs / Debuffs
- Letzte Episoden (5)
- Sidebar: Speichern / Laden / Reset

Hinweis: Prototype – kein finales Design.
