import time
import asyncio
from collections import deque

from core.models import WorldState, Decision
from core.actions import Dispatcher
from core.memory import MemoryManager
from core.logger import logger
from core.agents.security import SecurityAgent
from core.agents.comfort import ComfortAgent
from core.agents.energy import EnergyAgent
from core.agents.manager import ManagerAgent
from core.agents.orchestrator import ActionOrchestrator, ActionIntent


class Intelligence:
    def __init__(self, cooldown_seconds: float = 30.0):
        self.cooldown_seconds = cooldown_seconds
        self.last_consultation_time = time.time()
        self.recent_actions = deque(maxlen=10)  # Track last 10 actions
        self.llm_available = True

        # Initialize memory manager
        self.memory = MemoryManager()

        # Initialize specialist agents
        self.security_agent = SecurityAgent()
        self.comfort_agent = ComfortAgent()
        self.energy_agent = EnergyAgent()
        self.manager_agent = ManagerAgent()
        self.orchestrator = ActionOrchestrator()
        
        logger.info(
            "Mixture of Agents initialized",
            agents=["Security", "Comfort", "Energy", "Manager", "Orchestrator"],
            cooldown=cooldown_seconds,
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
            decision = await self._mixture_of_agents_decision(world)

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

    async def _mixture_of_agents_decision(
        self, world: WorldState
    ) -> Decision | None:
        """Consult all specialist agents in parallel, then Manager decides."""

        # Get memory context for each specialist (they filter by domain)
        security_memory = self.security_agent._get_memory_context(
            world, domain_filter=["lock", "binary_sensor", "alarm_control_panel"]
        )
        comfort_memory = self.comfort_agent._get_memory_context(
            world, domain_filter=["climate", "light", "switch", "fan", "cover"]
        )
        energy_memory = self.energy_agent._get_memory_context(
            world, domain_filter=["light", "switch", "climate", "fan", "media_player"]
        )

        # Consult all specialists in parallel
        logger.info("[MoA] Consulting specialist agents...")
        proposals = await asyncio.gather(
            self.security_agent.propose_action(world, security_memory),
            self.comfort_agent.propose_action(world, comfort_memory),
            self.energy_agent.propose_action(world, energy_memory),
            return_exceptions=True,
        )

        # Log each proposal
        for proposal in proposals:
            if isinstance(proposal, Exception):
                logger.error(f"[MoA] Agent error: {proposal}")
                continue

            action_str = (
                f"{proposal.decision.intent}" if proposal.decision else "null"
            )
            logger.info(
                f"[{proposal.agent_name}] Proposed: {action_str}",
                reasoning=proposal.reasoning,
                priority=proposal.priority_score,
                confidence=proposal.confidence,
            )

        # Filter out exceptions
        valid_proposals = [p for p in proposals if not isinstance(p, Exception)]

        # Manager arbitration (works with ActionIntent now)
        # Use general memory context for Manager
        manager_memory = self.security_agent._get_memory_context(world)
        final_proposal, manager_reasoning = await self.manager_agent.decide(
            valid_proposals, manager_memory
        )

        if not final_proposal:
            logger.info("[Manager] Final Decision: null", reasoning=manager_reasoning)
            return None

        # Convert ActionIntent to Decision via ActionOrchestrator
        if isinstance(final_proposal, ActionIntent):
            final_decision = self.orchestrator.format_decision(final_proposal, world)
            if final_decision:
                logger.info(
                    "[Manager] Final Decision",
                    action=final_decision.action,
                    entity=final_proposal.entity_name,
                    intent=final_proposal.intent,
                    reasoning=manager_reasoning,
                )
            else:
                logger.error(
                    "[Orchestrator] Failed to format decision",
                    intent=final_proposal.intent,
                )
            return final_decision
        else:
            logger.error(
                f"[Manager] Unexpected proposal type: {type(final_proposal)}"
            )
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

                self.memory.store(memory_text, memory_metadata)
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

                self.memory.store(memory_text, memory_metadata)
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
