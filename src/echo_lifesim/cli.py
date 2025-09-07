from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table
from .engine import LifeSimEngine
from pathlib import Path
from .llm_client import get_groq
from .persistence import save_state, load_state, export_state, DEFAULT_STATE_PATH
from .skills import load_skill_cards, autounlock_from_tests
from .world_assets import load_scenario, load_items_pack

app = typer.Typer(help="ECHO-LifeSim CLI")
console = Console()
engine = LifeSimEngine()

ONBOARD_HINTS = [
    "Beschreibe kurz deinen aktuellen inneren Zustand (z.B. 'etwas unruhig, will mich fokussieren').",
    "Nutze danach 'echo-sim act " + '"<Aktion>"' + "' um eine vorgeschlagene Mikro-Aktion auszuführen.",
    "Sieh dir mit 'echo-sim state' den Rohzustand an (Needs pendeln Richtung 50).",
    "Mit 'echo-sim epoch' forcierst du einen Epochenwechsel (Artefakt + evtl. Life-Phase).",
    "Verwende 'echo-sim scenario-set default' um ein Scenario zu setzen (Need-Drift).",
    "Nutze 'echo-sim chronicle-export chronicle.md' für eine Markdown-Lebenschronik.",
]

def maybe_onboarding() -> None:
    if engine.state.episodes:
        return
    console.rule("Willkommen bei ECHO-LifeSim (Erststart)")
    console.print("Kurzer Leitfaden – du hast noch keine Episoden.")
    for i,h in enumerate(ONBOARD_HINTS, start=1):
        console.print(f"[bold]{i}.[/bold] {h}")
    console.print("Starte jetzt z.B.:\n  echo-sim turn 'Bin etwas müde aber will einen klaren nächsten Schritt'\n")

maybe_onboarding()

@app.command()
def turn(text: str, event: str = typer.Option(None, help="Optional event key")) -> None:
    """Submit a user input line and get persona reply + suggestions."""
    result = engine.persona_reply(text, event_key=event)
    console.print(f"[bold cyan]Persona:[/bold cyan] {result['reply']}")
    if result["reflection"]:
        console.print(f"[magenta]{result['reflection']}[/magenta]")
    table = Table(title="Aktionen")
    table.add_column("Label")
    table.add_column("Dauer")
    for label, duration in result["actions"]:
        table.add_row(label, duration)
    console.print(table)
    needs_table = Table(title="Needs")
    for k in result["needs"].keys():
        needs_table.add_column(k)
    needs_table.add_row(*[str(v) for v in result["needs"].values()])
    console.print(needs_table)

@app.command()
def act(label: str = typer.Argument(..., help="Exact label of chosen action")) -> None:
    engine.apply_action_result(label)
    console.print("[green]Action applied.[/green]")

@app.command()
def state() -> None:
    """Dump raw PersonaState as JSON-like dict."""
    data = engine.state.model_dump()
    # attach lightweight overmind preview
    data['overmind_preview'] = {'thought_interval_ms': engine.state.thought_interval_ms}
    data['thought_count'] = len(engine.state.thoughts)
    console.print(data)

@app.command()
def thoughts(limit: int = typer.Option(10, help="Anzahl letzter Thoughts")) -> None:
    items = engine.state.thoughts[-limit:]
    if not items:
        console.print("[dim]Keine Thoughts bisher.[/dim]")
        return
    table = Table(title=f"Letzte {len(items)} Thoughts")
    table.add_column("Zeit")
    table.add_column("Text")
    for t in items:
        table.add_row(f"{int(t.ts)%86400}", t.text)
    console.print(table)

@app.command()
def reject() -> None:
    """Lehne aktuelle Vorschläge ab (Zähler erhöht, Streak reset)."""
    engine.reject_action()
    console.print("[yellow]Vorschläge abgelehnt.[/yellow]")

@app.command()
def thought_mute() -> None:
    engine.state.thought_mute = True
    console.print("[cyan]Thought-Ticker stumm geschaltet.[/cyan]")

@app.command()
def thought_unmute() -> None:
    engine.state.thought_mute = False
    console.print("[green]Thought-Ticker aktiv.[/green]")

@app.command()
def thought_interval(ms: int) -> None:
    engine.state.thought_interval_ms = max(1000, min(60000, ms))
    console.print({"thought_interval_ms": engine.state.thought_interval_ms})

@app.command()
def overmind() -> None:
    """Zeigt aktuelle Overmind-Anpassungen / Interval."""
    console.print({
        "thought_interval_ms": engine.state.thought_interval_ms,
        "streak": engine.state.success_streak,
        "accepted": engine.state.accepted_actions,
        "rejected": engine.state.rejected_actions,
        "om_intensity": engine.state.om_intensity,
        "om_variety": engine.state.om_variety,
        "om_suggestion_len": engine.state.om_suggestion_len,
    })

@app.command()
def overmind_set(
    intensity: int | None = typer.Option(None, help="1-3"),
    variety: int | None = typer.Option(None, help="1-3"),
    suggestion_len: int | None = typer.Option(None, help="1-4"),
) -> None:
    if intensity is not None:
        engine.state.om_intensity = max(1, min(3, intensity))
    if variety is not None:
        engine.state.om_variety = max(1, min(3, variety))
    if suggestion_len is not None:
        engine.state.om_suggestion_len = max(1, min(4, suggestion_len))
    console.print({
        "om_intensity": engine.state.om_intensity,
        "om_variety": engine.state.om_variety,
        "om_suggestion_len": engine.state.om_suggestion_len,
    })

@app.command()
def thought_max_len(value: int) -> None:
    engine.state.thought_max_len = max(40, min(400, value))
    console.print({"thought_max_len": engine.state.thought_max_len})

@app.command()
def skills_scan() -> None:
    cards = load_skill_cards()
    result = autounlock_from_tests(engine.state, cards)
    console.print(result)

@app.command()
def skills_list() -> None:
    cards = load_skill_cards()
    console.print({
        "available": list(cards.keys()),
        "unlocked": engine.state.unlocked_skills,
    })

@app.command()
def epoch() -> None:
    art = engine.state.advance_epoch()
    console.print({"epoch": engine.state.epoch, "artifact": art.title})

@app.command()
def artifacts() -> None:
    data = [a.model_dump() for a in engine.state.artifacts[-10:]]
    console.print(data or "(keine artifacts)")

@app.command()
def web_research_toggle() -> None:
    engine.state.web_research_enabled = not engine.state.web_research_enabled
    console.print({"web_research_enabled": engine.state.web_research_enabled})

@app.command()
def research(query: str) -> None:
    if not engine.state.web_research_enabled:
        console.print("[red]Web Research ist deaktiviert.[/red]")
        raise typer.Exit(1)
    # Placeholder simulated 3-2-1 output
    snippets = [
        {"src": "synth_1", "text": f"Zusammenfassung zu {query} (1)"},
        {"src": "synth_2", "text": f"Weitere Perspektive {query} (2)"},
        {"src": "synth_3", "text": f"Detailaspekt {query} (3)"},
    ]
    console.print({"query": query, "snippets": snippets})

@app.command()
def chronicle_export(path: str = "chronicle.md") -> None:
    text = engine.build_chronicle()
    from pathlib import Path
    Path(path).write_text(text, encoding="utf-8")
    console.print({"chronicle_export": path, "bytes": len(text)})

@app.command()
def auto_tick(steps: int = typer.Option(1, help="Anzahl autonomer Ticks")) -> None:
    out = []
    for _ in range(steps):
        out.append(engine.autonomous_tick())
    console.print(out)

@app.command()
def items() -> None:
    console.print([i.model_dump() for i in engine.state.items])

@app.command()
def add_item(name: str) -> None:
    from echo_lifesim.models import Item
    engine.state.items.append(Item(name=name))
    console.print({"added_item": name})

@app.command()
def mastery() -> None:
    console.print({"uses": engine.state.skill_uses, "levels": engine.state.skill_mastery})

@app.command()
def life_phase() -> None:
    console.print({"current": engine.state.life_phase, "history": engine.state.life_phase_history})

@app.command()
def scenario_set(name: str) -> None:
    scen = load_scenario(name)
    engine.state.world.scenario = scen.get("name", name)
    console.print({"scenario": engine.state.world.scenario})

@app.command()
def items_load(pack: str = "starter_pack.json") -> None:
    from echo_lifesim.models import Item
    data = load_items_pack(pack)
    added = []
    for it in data:
        try:
            engine.state.items.append(Item(**it))
            added.append(it.get("name"))
        except Exception:
            continue
    console.print({"loaded": added})

@app.command()
def save(path: str = typer.Option(str(DEFAULT_STATE_PATH), help="Datei für State")) -> None:
    save_state(engine.state, Path(path))
    console.print(f"[green]State gespeichert unter {path}[/green]")

@app.command()
def load(path: str = typer.Option(str(DEFAULT_STATE_PATH), help="Datei laden")) -> None:
    global engine
    engine = LifeSimEngine(load_state(Path(path)))
    console.print(f"[cyan]State geladen von {path}[/cyan]")

@app.command()
def export(path: str) -> None:
    export_state(Path(path))
    console.print(f"[green]Export erstellt: {path}[/green]")

@app.command()
def reset(confirm: bool = typer.Option(False, help="Mit --confirm bestätigen")) -> None:
    if not confirm:
        console.print("[red]Nutze --confirm zum Zurücksetzen[/red]")
        raise typer.Exit(1)
    global engine
    engine = LifeSimEngine()
    console.print("[yellow]State zurückgesetzt.[/yellow]")

@app.command()
def ping_llm() -> None:
    """Testet ob der GROQ_API_KEY funktioniert."""
    client = get_groq()
    result = client.ping()
    console.print(f"[blue]{result}[/blue]")

@app.command()
def llm_models() -> None:
    client = get_groq()
    models = client.list_models()
    hints = client.model_hints()
    console.print({"active": client.model, "available": {m: hints.get(m) for m in models}})

@app.command()
def set_model(name: str) -> None:
    client = get_groq()
    if client.set_model(name):
        console.print(f"[green]Modell gesetzt: {name}[/green]")
    else:
        console.print(f"[red]Unbekanntes Modell: {name}[/red]")

@app.command()
def help_start() -> None:
    """Zeigt kompakten Einstiegsleitfaden + erste Befehle."""
    for i,h in enumerate(ONBOARD_HINTS, start=1):
        console.print(f"[bold]{i}.\t[/bold]{h}")
    console.print("Beispiel: echo-sim turn 'Fühle mich zerstreut und will fokussieren' --event regen")

if __name__ == "__main__":
    app()
