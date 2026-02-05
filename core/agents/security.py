"""Security specialist agent - handles locks, sensors, and safety."""

import asyncio
import json
from ollama import chat, Message

from core.agents import BaseAgent, AgentProposal
from core.agents.orchestrator import ActionIntent
from core.models import WorldState
from core.logger import logger


class SecurityAgent(BaseAgent):
    """Specialist for security: locks, door sensors, motion sensors, alarms."""

    def __init__(self, model: str = "llama3.2:latest"):
        super().__init__(name="SecurityAgent", domain="security", model=model)

    async def propose_action(
        self, world_state: WorldState, memory_context: str
    ) -> AgentProposal:
        """Propose security-related actions."""

        # Filter to security-relevant entities
        security_domains = ["lock", "binary_sensor", "alarm_control_panel"]
        entities = self._filter_entities_by_domain(world_state, security_domains)

        if not entities:
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning="No security devices found in current state",
                confidence=1.0,
                priority_score=0.0,
            )

        # Build focused state summary
        state_lines = []
        for entity_id, name, state, ha_id in entities:
            state_lines.append(f"- {name} [UUID: {entity_id}] ({ha_id}): {state}")

        state_summary = "\n".join(state_lines)

        # Build focused prompt
        system_prompt = """You are a SECURITY specialist for a smart home. Your ONLY concern is safety and security.

FOCUS AREAS:
- Locks: Ensure doors are locked at night or when unoccupied
- Sensors: Respond to door/window open states, motion detection
- Safety: Prioritize preventing unauthorized access

RULES:
1. Only propose actions for locks, sensors, or alarms
2. If everything is secure, return null
3. Output simple intent (lock/unlock)
4. Assign priority_score 0.0-1.0 (0.9+ for urgent security issues)

Respond with JSON:
{
  "entity_name": "Front Door Lock" or null,
  "intent": "lock" or "unlock" or null,
  "reasoning": "why this action improves security",
  "priority_score": 0.0-1.0
}"""

        user_prompt = f"""SECURITY STATE:
{state_summary}

MEMORY CONTEXT:
{memory_context}

Decide ONE security action or return null if everything is secure."""

        # Call LLM in thread pool
        loop = asyncio.get_event_loop()
        response = await loop.run_in_executor(
            None,
            lambda: chat(
                model=self.model,
                messages=[
                    Message(role="system", content=system_prompt),
                    Message(role="user", content=user_prompt),
                ],
                format="json",
                options={"temperature": 0.3},
            ),
        )

        # Parse response
        try:
            result = json.loads(response.message.content)

            if result.get("entity_name") is None or result["entity_name"] == "null":
                return AgentProposal(
                    agent_name=self.name,
                    domain=self.domain,
                    decision=None,
                    reasoning=result.get("reasoning", "No security action needed"),
                    confidence=0.8,
                    priority_score=0.0,
                )

            # Store as intent (will be formatted by ActionOrchestrator)
            intent = ActionIntent(
                entity_name=result["entity_name"],
                intent=result.get("intent", "lock"),
                reasoning=result.get("reasoning", "Security action"),
            )

            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=intent,  # Store intent, not Decision
                reasoning=result.get("reasoning", "Security action needed"),
                confidence=0.8,
                priority_score=result.get("priority_score", 0.5),
            )

        except Exception as e:
            logger.error(f"[SecurityAgent] Failed to parse LLM response: {e}")
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning=f"Error parsing response: {e}",
                confidence=0.0,
                priority_score=0.0,
            )
