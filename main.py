import typer
import sys
from rich.console import Console
from rich.live import Live

from core.loader import DataLoader
from core.engine import SimulationEngine
from core.physics import PhysicsEngine
from core.intelligence import Intelligence
from core.logger import log_with_tui
from interfaces.tui import (
    print_splash_screen,
    render_layout,
    tui_mode,
    THEME_COLOR,
)

app = typer.Typer()
console = Console()


@app.command()
def start(config: str = "./simulations/home.yaml"):
    """
    Lifecycle:
    1. Splash screen (pre-TUI)
    2. Load world state from config
    3. Enter TUI mode and run simulation loop:
       - Physics: Update world state
       - Intelligence: Make decisions
       - Actions: Execute decisions
       - Observer: Refresh TUI display
    """
    # 1. SPLASH SCREEN PHASE
    print_splash_screen(console)
    try:
        input()
    except KeyboardInterrupt:
        console.print("\nAborted.", style="red")
        sys.exit(0)

    console.print("\n🚀 Initializing Core Runtime...", style=THEME_COLOR)

    dataloader = DataLoader()
    intelligence = Intelligence()
    sim_engine = SimulationEngine(step=1)

    world_state, physics_data = dataloader.load(config)

    phy_engine = PhysicsEngine(physics_data=physics_data)

    if not world_state:
        console.print(
            f"Critical Error: Could not load configuration at {config}",
            style="bold red",
        )
        sys.exit(1)

    try:
        with (
            tui_mode(),
            Live(render_layout(world_state), refresh_per_second=4, screen=True) as live,
        ):
            log_with_tui("info", "system_loaded", entities=len(world_state.entities))

            sim_engine.run_loop(
                world_state=world_state,
                physics_fn=phy_engine.apply_physics,
                decision_fn=intelligence.make_decision,
                action_fn=intelligence.apply_action,
                log_fn=lambda state: live.update(render_layout(state)),
            )

    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n Simulation Stopped.", style="bold red")


if __name__ == "__main__":
    app()
