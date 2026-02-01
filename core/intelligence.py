import time
from collections import deque

from core.models import WorldState, Decision
from core.actions import Dispatcher
from core.llm import Instructor
from core.logger import logger


class Intelligence:
    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_consultation_time = time.time()
        self.recent_actions = deque(maxlen=10)  # Track last 10 actions

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

        # Get entity state before action
        entity = world.get_entity_by_id(decision.target_entity_id)
        state_before = entity.attributes.copy() if entity else {}

        # Execute the decision
        try:
            self.dispatcher.dispatch(world=world, decision=decision)

            # Get entity state after action
            entity_after = world.get_entity_by_id(decision.target_entity_id)
            state_after = entity_after.attributes.copy() if entity_after else {}

            # Track this action for correction detection
            action_record = {
                "timestamp": time.time(),
                "decision": decision,
                "entity_id": decision.target_entity_id,
                "entity_name": entity.name
                if entity
                else str(decision.target_entity_id),
                "state_before": state_before,
                "state_after": state_after,
            }
            self.recent_actions.append(action_record)

            # Store successful decision in memory
            try:
                entity_name = entity.name if entity else str(decision.target_entity_id)

                memory_text = f"Action: {decision.action} on {entity_name}. Reasoning: {decision.reasoning}"
                memory_metadata = {
                    "timestamp": time.time(),
                    "action": decision.action,
                    "entity_id": str(decision.target_entity_id),
                    "entity_name": entity_name,
                    "success": True,
                }

                self.instructor.memory.store(memory_text, memory_metadata)
                logger.debug("Decision stored in memory", action=decision.action)
            except Exception as mem_error:
                logger.warning("Memory store failed", error=str(mem_error))

        except Exception as e:
            # Store failed decision in memory
            try:
                entity_name = entity.name if entity else str(decision.target_entity_id)

                memory_text = f"Action FAILED: {decision.action} on {entity_name}. Error: {str(e)}. Reasoning: {decision.reasoning}"
                memory_metadata = {
                    "timestamp": time.time(),
                    "action": decision.action,
                    "entity_id": str(decision.target_entity_id),
                    "entity_name": entity_name,
                    "success": False,
                    "error": str(e),
                }

                self.instructor.memory.store(memory_text, memory_metadata)
                logger.error(
                    "Decision failed and logged to memory",
                    action=decision.action,
                    error=str(e),
                )
            except Exception as mem_error:
                logger.warning("Memory store failed for error", error=str(mem_error))

            raise

    def get_recent_actions(self, within_seconds: int = 300) -> list[dict]:
        """Get recent actions within specified time window."""
        cutoff_time = time.time() - within_seconds
        return [
            action
            for action in self.recent_actions
            if action["timestamp"] >= cutoff_time
        ]
