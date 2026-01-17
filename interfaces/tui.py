from collections import deque
from datetime import datetime
from contextlib import contextmanager
from rich.layout import Layout
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.console import Console
from rich.style import Style
from rich import box
from pyfiglet import Figlet
from core.models import WorldState

# --- THEME CONSTANTS ---
THEME_COLOR = "#F85E00"
THEME_STYLE = Style(color=THEME_COLOR, bold=True)
BORDER_STYLE = Style(color=THEME_COLOR, dim=True)

console = Console()

log_buffer = deque(maxlen=8)

_tui_active = False


def is_tui_active() -> bool:
    return _tui_active


@contextmanager
def tui_mode():
    global _tui_active
    _tui_active = True
    try:
        yield
    finally:
        _tui_active = False


def add_log_to_buffer(message: str):
    timestamp = datetime.now().strftime("%H:%M:%S")
    log_buffer.append(f"[{timestamp}] {message}")


def print_splash_screen(console: Console):
    """Renders the startup splash screen."""
    console.clear()

    welcome_text = Text("Welcome to the ", style="dim white")
    welcome_text.append("Agentic Home Automation Engine", style="bold white")

    console.print(
        Panel(
            welcome_text,
            border_style=THEME_COLOR,
            padding=(0, 2),
            width=60,
            title="*",
            title_align="left",
        )
    )
    console.print()

    f = Figlet(font="ansi_shadow", width=100)
    console.print(Text(f.renderText("FARZ"), style=THEME_COLOR))
    console.print(Text(f.renderText("HOME"), style=THEME_COLOR))
    console.print()

    status_text = Text("🎉 System Ready. Press ", style="dim white")
    status_text.append("Enter", style="bold white")
    status_text.append(" to initialize simulation...", style="dim white")
    console.print(status_text)


def generate_header(world: WorldState) -> Panel:
    grid = Table.grid(expand=True)
    grid.add_column(justify="left", ratio=1)
    grid.add_column(justify="center", ratio=1)
    grid.add_column(justify="right", ratio=1)

    title = Text("FARZ HOME", style=THEME_STYLE)
    subtitle = Text(" | Reality Engine", style="dim white")
    
    # Global attributes display
    global_attrs = world.global_attributes
    time_of_day = global_attrs.get("time_of_day", 0.0)
    weather = global_attrs.get("weather", "unknown")
    outdoor_temp = global_attrs.get("outdoor_temperature", 0.0)
    
    # Format time as HH:MM
    hours = int(time_of_day)
    minutes = int((time_of_day - hours) * 60)
    time_str = f"{hours:02d}:{minutes:02d}"
    
    # Weather emoji mapping
    weather_icons = {
        "sunny": "☀️",
        "clear": "☀️",
        "partly_cloudy": "⛅",
        "cloudy": "☁️",
        "overcast": "🌥️",
        "rainy": "🌧️",
        "stormy": "⛈️",
        "snowy": "❄️",
    }
    weather_icon = weather_icons.get(weather, "🌤️")
    
    global_display = Text(f"{time_str} {weather_icon} {outdoor_temp:.1f}°C", style="cyan")
    
    clock = Text(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="dim white")

    grid.add_row(title + subtitle, global_display, clock)
    return Panel(grid, style=BORDER_STYLE, box=box.SIMPLE)


def generate_entity_table(world: WorldState, height: int | None = None) -> Panel:
    """
    Renders the live entity state.
    ADAPTIVE: If 'height' is provided, we limit the rows to fit.
    """
    table = Table(expand=True, border_style="dim", box=None)

    table.add_column("ID", style="dim cyan", no_wrap=True, width=8)
    table.add_column("Entity Name", style="bold white")
    table.add_column("State / Attributes", style="yellow")
    table.add_column("Tags", style="dim magenta")

    all_entities = sorted(world.entities.values(), key=lambda e: e.name)

    # --- ADAPTIVE TRUNCATION LOGIC ---
    # Estimate available rows (Header=2, Borders=2)
    max_rows = (height - 4) if height else 100

    visible_entities = all_entities[:max_rows]
    hidden_count = len(all_entities) - len(visible_entities)

    for entity in visible_entities:
        attr_text = Text()
        for i, (k, v) in enumerate(entity.attributes.items()):
            if i > 0:
                attr_text.append(" | ", style="dim")
            attr_text.append(f"{k}: ", style="dim")
            val_style = (
                "green"
                if v == "ON" or v is True
                else "red"
                if v == "OFF" or v is False
                else "cyan"
            )
            val_str = f"{v:.2f}" if isinstance(v, float) else str(v)
            attr_text.append(val_str, style=val_style)

        table.add_row(
            str(entity.id)[:8], entity.name, attr_text, ", ".join(entity.tags)
        )

    # If we hid some, show a summary row
    if hidden_count > 0:
        table.add_row(
            "...", f"[i dim]... and {hidden_count} more entities ...[/]", "", ""
        )

    return Panel(
        table,
        title=f"[b]Active Entities ({len(world.entities)})[/b]",
        border_style=BORDER_STYLE,
        box=box.HEAVY,
    )


def generate_log_panel() -> Panel:
    text = Text()
    for log in log_buffer:
        text.append(log + "\n")

    return Panel(
        text,
        title="[b]System Events[/b]",
        border_style="white",
        box=box.ROUNDED,
        height=10,
    )


def render_layout(world: WorldState) -> Layout:
    layout = Layout()

    layout.split_column(
        Layout(name="header", size=3), Layout(name="body"), Layout(name="logs", size=10)
    )

    # Calculate how tall the body is allowed to be
    # total_height - header(3) - logs(10)
    term_height = console.height
    body_height = term_height - 13

    layout["header"].update(generate_header(world))
    layout["body"].update(generate_entity_table(world, height=body_height))
    layout["logs"].update(generate_log_panel())

    return layout
