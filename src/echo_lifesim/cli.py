from __future__ import annotations
import typer
from rich.console import Console
from rich.table import Table
from .engine import LifeSimEngine
from pathlib import Path
from .llm_client import get_groq
from .persistence import save_state, load_state, export_state, DEFAULT_STATE_PATH
from .skills import load_skill_cards, autounlock_from_tests

app = typer.Typer(help="ECHO-LifeSim CLI")
console = Console()
engine = LifeSimEngine()

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

if __name__ == "__main__":
    app()
