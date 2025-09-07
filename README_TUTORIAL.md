# ECHO-LifeSim Einstieg & Tutorial

Willkommen! Dieses Tutorial führt dich in die Simulation ein und zeigt dir konkrete erste Schritte, Eingaben und Interaktionsmöglichkeiten.

## 1. Ziel der Simulation
Du steuerst einen KI-Persona-Zustand mit Bedürfnissen (Energie, Fokus, Stimmung, Sozial, Klarheit usw.). Du gibst kurze Impulse (Gedanken, Situationen, Fragen). Das System antwortet als Spiegel und schlägt zwei passende Mikro-Aktionen (A/B) vor. Du entscheidest, was ausgeführt wird. Nebenbei entstehen Episoden, Artefakte, Träume, Achievements und eine Lebens-Chronik.

## 2. Schnellstart
```powershell
# Abhängigkeiten (inkl. GUI) installieren
pip install -e .[gui]

# CLI starten – ersten Turn senden
echo-sim turn "Ich bin leicht gestresst und will klarer denken" --event regen

# Erste Aktion ausführen (Label aus Vorschlag kopieren)
echo-sim act "2-Min atemfokus"

# State ansehen
echo-sim state
```

## 3. Wichtige Konzepte
- Needs: Pendeln um ~50. Hohe Abweichung deutet auf dysbalance → passende Aktionen helfen.
- Episode: Jede Interaktion (User, Persona, Event, Reflection, Action, Dream).
- Topic: Verwandte Episoden werden gruppiert (Tabs in der GUI).
- Overmind: Adaptive Parameter (Gedankenfrequenz, Vielfalt) – reagiert auf Erfolg/Misserfolg.
- Achievements & Stats: Bestimmte Muster schalten Erfolge frei und erhöhen z.B. Insight.
- Mastery: Wiederholte Skill-Nutzung steigert Mastery-Level (z.B. web_research_3_2_1: 1→2→3…).
- Dream: In der Night-Phase einmal pro Zyklus möglich – kann ein Artefakt erzeugen.
- Scenario: Umgebung mit Need-Drift & Event-Bias (z.B. Fokus-Drift, soziale Flaute).
- Chronicle: Markdown-Lebenslauf exportierbar.

## 4. Typischer Ablauf (Loop)
1. Du beschreibst Zustand / Frage.
2. (Optional) Event auswählen zur Kontextanreicherung.
3. System antwortet + 2 Aktionsvorschläge.
4. Du führst 0–1 Aktionen aus (`echo-sim act <Label>` oder GUI Button).
5. Gedanken & Reflexionen entstehen periodisch automatisch.
6. Epoch-Wechsel generiert evtl. Artefakt + Phase-Check.

## 5. Beispiel-Eingaben
Versuche abwechslungsreiche, ehrliche kurze Texte:
- "Bin müde aber will etwas lernen."  
- "Zu viele Tabs offen, Kopf voll."  
- "Motivation ist weg – was jetzt klein anfangen?"  
- "Habe eine Idee, aber zweifle ob sie sinnvoll ist."  
- "Fühle mich isoliert – brauche Connection."  

## 6. Aktionen interpretieren
Vorschläge sind Mikro-Schritte (1–5 Minuten) oder mentale Umfokusierungen. Nimm die, die sich realistisch anfühlt. Wiederholung baut Mastery auf.

## 7. Weitere nützliche CLI Kommandos
```powershell
# Achievements & Stats indirekt sehen (im state dump)
echo-sim state

# Epoch voranschieben (Test)
echo-sim epoch

# Items anzeigen / hinzufügen
echo-sim items
# (Beispiel Item hinzufügen)
echo-sim add-item "Mentales Fokusband"

# Mastery aktueller Skills
echo-sim mastery

# Life Phase anzeigen
echo-sim life-phase

# Scenario setzen (entspricht Dateiname in scenarios/ ohne .json)
echo-sim scenario-set default

# Item-Pack laden
echo-sim items-load starter_pack.json

# Autonomes Ticken (z.B. 5 Ticks)
echo-sim auto-tick 5

# Chronicle export als Markdown anzeigen
echo-sim chronicle-export chronicle.md
```

## 8. GUI Start (Streamlit)
```powershell
streamlit run src/echo_lifesim/gui.py
```
Features: Topic-Tabs, letzte Episoden, Needs-Balken, Mastery, Achievements, Phase, Export-Button.

Falls Start fehlschlägt: Prüfe Installation `pip install -e .[gui]` und Python-Version >=3.11.

## 9. Tipps für den Einstieg
- Starte mit 3–5 kurzen Runden, führe nur eine der beiden Aktionen aus.
- Achte darauf, wie Needs sich langsam Richtung Mitte bewegen.
- Nutze einmal `epoch` nach ~8–10 Interaktionen um Artefakt/Phase zu sehen.
- Beobachte Gedanken (🧠) – sie zeigen interne Adaption.
- Wechsel das Scenario, um anderes Grundverhalten (Need Drift) zu spüren.

## 10. Häufige Fragen
Q: Warum wiederholen sich manche Aktionen?  
A: Variety-Logik balanciert Nutzen vs. Wiederholung; mehr Mastery erweitert Pool.  
Q: Was bringt Mastery?  
A: Reduziert Varianz & steigert qualitative Wirkung (geplantes Feintuning).  
Q: Kann ich mehrere Aktionen pro Turn ausführen?  
A: Ja, technisch möglich – aber für Balance 1 wählen.  
Q: Wie speichere ich dauerhaft?  
A: GUI Sidebar "State speichern" oder CLI `echo-sim save`.  

## 11. Nächste Ausbaustufen (Ausblick)
- Sicherheits-/Inhaltsfilter
- Erweiterte Web Recherche (echte API)
- Mehr Szenarien & Event-getriggerte Mikro-Storylines
- Multi-Lebens Archiv & Generationsvergleich

Viel Spaß – probiere einfach eine erste Eingabe wie:
"Fühle mich zerstreut, will einen ruhigen klaren Schritt finden."

Dann eine Aktion auswählen und beobachten wie sich Fokus / Klarheit entwickeln.

---
Feedback willkommen. Schreib einfach was dir fehlt.
