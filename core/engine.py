import time
import signal

from typing import Callable

from core.models import WorldState, Decision
from core.logger import log_with_tui


class SimulationEngine:
    def __init__(self, step: float = 1.0):
        self.step = step
        self._running = False

    def _setup_signal_handling(self):
        """Only attach signals when we actually intend to run forever."""
        signal.signal(signal.SIGINT, self._stop)

    def _stop(self, signum, frame):
        self._running = False
        log_with_tui("info", "shutting_down_simulation")

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
                        log_with_tui(
                            "info",
                            "agent_decision",
                            action=decision.action,
                            target=str(decision.target_entity_id),
                            reason=decision.reasoning,
                        )

                        # --- PHASE 3: ACTUATOR (The Hands) ---
                        if action_fn:
                            action_fn(world_state, decision)
                        else:
                            log_with_tui("warning", "decision_made_but_no_action_handler")

                # --- PHASE 4: OBSERVABILITY ---
                if log_fn:
                    log_fn(world_state)

                # Heartbeat
                if self.step > 0:
                    time.sleep(self.step)

                ticks += 1

            except Exception as e:
                log_with_tui("error", "sim_loop_crash", error=str(e))
                if max_ticks:
                    raise e
                time.sleep(self.step)
