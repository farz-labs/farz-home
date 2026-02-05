"""Energy specialist agent - handles power consumption and cost optimization."""

import asyncio
import json
from ollama import chat, Message

from core.agents import BaseAgent, AgentProposal
from core.agents.orchestrator import ActionIntent
from core.models import WorldState
from core.logger import logger


class EnergyAgent(BaseAgent):
    """Specialist for energy: power consumption, cost optimization."""

    def __init__(self, model: str = "llama3.2:latest"):
        super().__init__(name="EnergyAgent", domain="energy", model=model)

    async def propose_action(
        self, world_state: WorldState, memory_context: str
    ) -> AgentProposal:
        """Propose energy-saving actions."""

        # Filter to energy-relevant entities (power sensors + controllables)
        all_entities = []
        power_sensors = []

        for entity in world_state.entities.values():
            ha_entity_id = entity.attributes.get("ha_entity_id", "")
            domain = ha_entity_id.split(".")[0] if "." in ha_entity_id else ""
            state = entity.attributes.get("state", "unknown")

            # Track power sensors
            if "power" in ha_entity_id.lower() or "energy" in ha_entity_id.lower():
                power_sensors.append(f"- {entity.name} ({ha_entity_id}): {state}")

            # Track controllable devices that consume power
            if domain in ["light", "switch", "climate", "fan", "media_player"]:
                all_entities.append(
                    (entity.id, entity.name, state, ha_entity_id, domain)
                )

        if not all_entities and not power_sensors:
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning="No energy-consuming devices found",
                confidence=1.0,
                priority_score=0.0,
            )

        # Build state summary
        state_lines = []
        if power_sensors:
            state_lines.append("POWER SENSORS:")
            state_lines.extend(power_sensors)
            state_lines.append("")

        state_lines.append("CONTROLLABLE DEVICES:")
        for entity_id, name, state, ha_id, domain in all_entities:
            state_lines.append(f"- {name} [UUID: {entity_id}] ({ha_id}): {state}")

        state_summary = "\n".join(state_lines)

        # Build focused prompt
        system_prompt = """You are an ENERGY specialist for a smart home. Your ONLY concern is minimizing power consumption and costs.

FOCUS AREAS:
- Waste reduction: Turn off unused lights, devices, climate control
- Efficiency: Suggest lower power modes when appropriate
- Cost: Minimize unnecessary energy consumption

AVAILABLE INTENTS:
- turn_off (to reduce consumption)
- turn_on (only if needed for efficiency)

RULES:
1. Only propose actions that REDUCE energy consumption
2. If energy use is already minimal, return null
3. Do NOT compromise safety (e.g., don't turn off security lights at night)
4. Assign priority_score 0.0-1.0 (0.6+ for significant waste detected)

Respond with JSON:
{
  "entity_name": "Bedroom Light" or null,
  "intent": "turn_off" or null,
  "reasoning": "why this saves energy",
  "priority_score": 0.0-1.0
}"""

        user_prompt = f"""ENERGY STATE:
{state_summary}

MEMORY CONTEXT:
{memory_context}

Decide ONE energy-saving action or return null if energy use is optimized."""

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
                    reasoning=result.get("reasoning", "No energy-saving action needed"),
                    confidence=0.8,
                    priority_score=0.0,
                )

            # Store as intent (will be formatted by ActionOrchestrator)
            intent = ActionIntent(
                entity_name=result["entity_name"],
                intent=result.get("intent", "turn_off"),
                reasoning=result.get("reasoning", "Energy-saving action"),
            )

            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=intent,  # Store intent, not Decision
                reasoning=result.get("reasoning", "Energy-saving action needed"),
                confidence=0.8,
                priority_score=result.get("priority_score", 0.5),
            )

        except Exception as e:
            logger.error(f"[EnergyAgent] Failed to parse LLM response: {e}")
            return AgentProposal(
                agent_name=self.name,
                domain=self.domain,
                decision=None,
                reasoning=f"Error parsing response: {e}",
                confidence=0.0,
                priority_score=0.0,
            )
