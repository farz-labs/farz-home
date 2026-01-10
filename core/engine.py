import time
import signal

from typing import Callable
from functools import partial

from core.models import WorldState, Decision
from core.intelligence import make_decision
from core.logger import app_logger
from core.utils import increment_attribute, log_attribute


class SimulationEngine:
    def __init__(self, step: float = 1.0):
        self.step = step
        self._running = False

    def _setup_signal_handling(self):
        """Only attach signals when we actually intend to run forever."""
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, signum, frame):
        self._running = False
        app_logger.info("Shutting down simulation...")

    def run_loop(
        self,
        world_state: WorldState,
        physics_fn: Callable[[WorldState], None],
        decision_fn: Callable[[WorldState], Decision | None] | None = None,
        action_fn: Callable[[WorldState, Decision], None] | None = None,
        log_fn: Callable[[WorldState], None] | None = None,
        max_ticks: int | None = None,
    ) -> None:
        """
        Runs the Generic Reality Engine.
        Cycle: Physics -> Observe -> Decide -> Act
        """
        self._running = True
        if max_ticks is None:
            self._setup_signal_handling()

        ticks = 0

        while self._running:
            try:
                if max_ticks and ticks >= max_ticks:
                    break

                # --- PHASE 1: PHYSICS (Entropy) ---
                physics_fn(world_state)

                # --- PHASE 2: INTELLIGENCE (The Brain) ---
                if decision_fn:
                    decision = decision_fn(world_state)

                    if decision:
                        app_logger.info(
                            "agent_decision",
                            action=decision.action,
                            target=str(decision.target_entity_id),
                            reason=decision.reasoning,
                        )

                        # --- PHASE 3: ACTUATOR (The Hands) ---
                        if action_fn:
                            action_fn(world_state, decision)
                        else:
                            app_logger.warning("decision_made_but_no_action_handler")

                # --- PHASE 4: OBSERVABILITY ---
                if log_fn:
                    log_fn(world_state)

                # Heartbeat
                if self.step > 0:
                    time.sleep(self.step)

                ticks += 1

            except Exception as e:
                app_logger.error("sim_loop_crash", error=str(e))
                if max_ticks:
                    raise e
                time.sleep(self.step)


def run_living_room_simulation(
    world_state: WorldState, engine: SimulationEngine | None = None
):
    sim_engine = engine or SimulationEngine(step=0.5)

    target = next(
        e for e in world_state.entities.values() if e.name == "Living Room Light"
    )

    update_brightness = partial(
        increment_attribute,
        entity_name=target.name,
        attribute_name="brightness",
        delta=0.1,
        default=0.0,
    )

    log_brightness = partial(
        log_attribute,
        entity_name=target.name,
        attribute_name="brightness",
    )

    sim_engine.run_loop(
        world_state=world_state,
        physics_fn=update_brightness,
        decision_fn=make_decision,
        log_fn=log_brightness,
    )
