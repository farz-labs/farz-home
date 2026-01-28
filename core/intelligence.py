import time

from core.models import WorldState, Decision
from core.actions import Dispatcher
from core.llm import Instructor
from core.logger import logger


class Intelligence:
    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_consultation_time = time.time()

        try:
            self.instructor = Instructor()
            self.llm_available = True
            logger.info("LLM initialized", cooldown=cooldown_seconds)
        except ValueError as e:
            self.llm_available = False
            logger.error(
                "LLM initialization failed",
                reason=str(e),
                solution="Set GEMINI_API_KEY environment variable",
            )

        self.dispatcher = Dispatcher.get_instance()

    async def make_decision_async(self, world: WorldState) -> Decision | None:
        """Async version that runs LLM in thread pool to avoid blocking."""
        if not self.llm_available:
            return None

        current_time = time.time()
        time_since_last_consultation = current_time - self.last_consultation_time

        if time_since_last_consultation < self.cooldown_seconds:
            remaining = self.cooldown_seconds - time_since_last_consultation
            logger.debug(
                "LLM cooldown active",
                remaining_seconds=round(remaining, 1),
            )
            return None

        logger.info(
            "LLM consultation starting",
            entities_count=len(world.entities),
            time_since_last=round(time_since_last_consultation, 1),
        )

        self.last_consultation_time = time.time()

        try:
            import asyncio

            loop = asyncio.get_event_loop()
            decision = await loop.run_in_executor(
                None, self.instructor.consult_oracle, world
            )

            if decision:
                logger.info(
                    "Decision cooldown reset",
                    next_available_seconds=self.cooldown_seconds,
                )
            else:
                logger.info("LLM returned none")

            return decision
        except Exception as e:
            logger.error("Decision failed", error=str(e))
            self.last_consultation_time = time.time()
            return None

    def make_decision(self, world: WorldState) -> Decision | None:
        """Sync version for TUI mode compatibility."""
        if not self.llm_available:
            return None

        current_time = time.time()
        time_since_last = current_time - self.last_consultation_time

        if time_since_last < self.cooldown_seconds:
            return None

        self.last_consultation_time = time.time()

        try:
            decision = self.instructor.consult_oracle(world_state=world)
            return decision
        except Exception as e:
            logger.error("Decision failed", error=str(e))
            return None

    def apply_action(self, world: WorldState, decision: Decision):
        logger.info(
            "Applying decision",
            action=decision.action,
            target=str(decision.target_entity_id)[:8],
        )
        self.dispatcher.dispatch(world=world, decision=decision)
