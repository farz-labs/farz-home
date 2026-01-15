import time

from core.models import WorldState, Decision
from core.actions import Dispatcher
from core.llm import Instructor
from core.logger import log_with_tui


class Intelligence:
    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_consultation_time = time.time()

        try:
            self.instructor = Instructor()
            self.llm_available = True
            log_with_tui("info", "llm_initialized", cooldown=cooldown_seconds)
        except ValueError as e:
            self.llm_available = False
            log_with_tui(
                "error",
                "llm_initialization_failed",
                reason=str(e),
                solution="Set GEMINI_API_KEY environment variable",
            )

        self.dispatcher = Dispatcher.get_instance()

    def make_decision(self, world: WorldState) -> Decision | None:
        if not self.llm_available:
            return None

        current_time = time.time()
        time_since_last_consultation = current_time - self.last_consultation_time

        if time_since_last_consultation < self.cooldown_seconds:
            remaining = self.cooldown_seconds - time_since_last_consultation
            log_with_tui(
                "debug",
                "llm_cooldown_active",
                remaining_seconds=round(remaining, 1),
            )
            return None

        log_with_tui(
            "info",
            "llm_consultation_starting",
            entities_count=len(world.entities),
            time_since_last=round(time_since_last_consultation, 1),
        )

        self.last_consultation_time = time.time()

        try:
            decision = self.instructor.consult_oracle(world_state=world)

            if decision:
                log_with_tui(
                    "info",
                    "decision_cooldown_reset",
                    next_available_seconds=self.cooldown_seconds,
                )
            else:
                log_with_tui("info", "llm_returned_none")

            return decision
        except Exception as e:
            log_with_tui("error", "decision_failed", error=str(e))
            self.last_consultation_time = time.time()
            return None

    def apply_action(self, world: WorldState, decision: Decision):
        log_with_tui(
            "info",
            "applying_decision",
            action=decision.action,
            target=str(decision.target_entity_id)[:8],
        )
        self.dispatcher.dispatch(world=world, decision=decision)
