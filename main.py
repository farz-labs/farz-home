import typer
import sys
import time
from functools import partial
from rich.console import Console
from rich.live import Live

from core.loader import DataLoader
from core.engine import SimulationEngine
from core.models import WorldState
from core.utils import increment_attribute
from interfaces.tui import (
    print_splash_screen,
    render_layout,
    add_log_to_buffer,
    THEME_COLOR,
)

app = typer.Typer()
console = Console()


@app.command()
def start(config: str = "./simulations/home.yaml"):
    """
    Starts the Farz Home Simulation Engine.
    """
    # 1. SPLASH SCREEN PHASE
    print_splash_screen(console)
    try:
        input()
    except KeyboardInterrupt:
        console.print("\nAborted.", style="red")
        sys.exit(0)

    console.print("\n🚀 Initializing Core Runtime...", style=THEME_COLOR)
    time.sleep(0.5)

    # 2. INITIALIZATION PHASE
    loader = DataLoader()
    world_state = loader.load(config)

    if not world_state:
        console.print(
            f"❌ Critical Error: Could not load configuration at {config}",
            style="bold red",
        )
        sys.exit(1)

    add_log_to_buffer(f"System loaded with {len(world_state.entities)} entities.")
    sim_engine = SimulationEngine(step=0.5)

    # 3. SETUP SIMULATION LOGIC (PHYSICS)
    target_name = "Living Room Light"

    # We must ensure the entity exists to avoid crash
    try:
        target = next(e for e in world_state.entities.values() if e.name == target_name)

        physics_logic = partial(
            increment_attribute,
            entity_name=target.name,
            attribute_name="brightness",
            delta=0.1,
            default=0.0,
        )
    except StopIteration:

        def physics_logic(w):
            return None

        add_log_to_buffer(f"Warning: '{target_name}' not found. Physics disabled.")

    # 4. RUNTIME LOOP (RICH LIVE)
    try:
        with Live(
            render_layout(world_state), refresh_per_second=4, screen=True
        ) as live:

            def tui_observer(state: WorldState):
                """Callback: Updates the screen and logs specific changes."""
                # Check for changes to log (simplified)
                # In a real system, we'd compare state diffs
                live.update(render_layout(state))

                # Hacky log for visual feedback
                val = state.get_attribute_value(target.id, "brightness")
                if val and isinstance(val, float) and int(val * 10) % 5 == 0:
                    add_log_to_buffer(
                        f"Sensor Update: {target.name} brightness is {val:.1f}"
                    )

            # Start the infinite loop
            # Note: We use 'physics_fn' as per the rigorous architecture definition
            sim_engine.run_loop(
                world_state=world_state,
                physics_fn=physics_logic,
                log_fn=tui_observer,
            )

    except KeyboardInterrupt:
        pass
    finally:
        console.print("\n Simulation Stopped.", style="bold red")


if __name__ == "__main__":
    app()
