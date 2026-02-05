"""Comfort specialist agent - handles temperature, lighting, and ambiance."""

import asyncio
import json
from ollama import chat, Message

from core.agents import BaseAgent, AgentProposal
from core.agents.orchestrator import ActionIntent
from core.models import WorldState
from core.logger import logger


class ComfortAgent(BaseAgent):
    """Specialist for comfort: climate control, lighting, switches."""

    def __init__(self, model: str = "llama3.2:latest"):
        super().__init__(name="ComfortAgent", domain="comfort", model=model)

    async def propose_action(
        self, world_state: WorldState, memory_context: str
    ) -> AgentProposal:
        """Propose comfort-related actions."""

        # Filter to comfort-relevant entities
        comfort_domains = ["climate", "light", "switch", "fan", "cover"]
        entities = self._filter_entities_by_domain(world_state, comfort_domains)

        # Also get context (sun, weather)
        context_entities = self._filter_entities_by_domain(
            world_state, ["sun", "weather"]
        )

        if not entities:
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning="No comfort devices found in current state",
                confidence=1.0,
                priority_score=0.0,
            )

        # Build focused state summary
        state_lines = []
        for entity_id, name, state, ha_id in entities:
            state_lines.append(f"- {name} [UUID: {entity_id}] ({ha_id}): {state}")

        if context_entities:
            state_lines.append("\nCONTEXT:")
            for entity_id, name, state, ha_id in context_entities:
                state_lines.append(f"- {name} [UUID: {entity_id}]: {state}")

        state_summary = "\n".join(state_lines)

        # Build focused prompt
        system_prompt = """You are a COMFORT specialist for a smart home. Your ONLY concern is user comfort and convenience.

FOCUS AREAS:
- Temperature: Maintain comfortable climate
- Lighting: Adjust brightness and state based on time of day
- Ambiance: Manage fans, covers, switches for comfort

AVAILABLE INTENTS:
- turn_on, turn_off, toggle (lights, switches, fans)
- set_temperature_X (climate, where X is degrees)
- set_brightness_X (lights, where X is 0-255)

RULES:
1. Only propose actions for climate, light, switch, fan, cover domains
2. If comfort is optimal, return null
3. Consider time of day (sun position) and weather
4. Assign priority_score 0.0-1.0 (0.7+ for significant discomfort)

Respond with JSON:
{
  "entity_name": "Living Room Light" or null,
  "intent": "turn_on" or "set_temperature_22" or null,
  "reasoning": "why this improves comfort",
  "priority_score": 0.0-1.0
}"""

        user_prompt = f"""COMFORT STATE:
{state_summary}

MEMORY CONTEXT:
{memory_context}

Decide ONE comfort action or return null if comfort is optimal."""

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
                    reasoning=result.get("reasoning", "No comfort action needed"),
                    confidence=0.8,
                    priority_score=0.0,
                )

            # Store as intent (will be formatted by ActionOrchestrator)
            intent = ActionIntent(
                entity_name=result["entity_name"],
                intent=result.get("intent", "turn_on"),
                reasoning=result.get("reasoning", "Comfort action"),
            )

            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=intent,  # Store intent, not Decision
                reasoning=result.get("reasoning", "Comfort action needed"),
                confidence=0.8,
                priority_score=result.get("priority_score", 0.5),
            )

        except Exception as e:
            logger.error(f"[ComfortAgent] Failed to parse LLM response: {e}")
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning=f"Error parsing response: {e}",
                confidence=0.0,
                priority_score=0.0,
            )
