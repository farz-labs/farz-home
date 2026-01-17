import json
from dotenv import load_dotenv

from ollama import chat, ChatResponse, Message

from core.models import WorldState, Decision
from core.actions import ActionType
from core.logger import log_with_tui

load_dotenv()


class Instructor:
    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model
        self.last_decision: Decision | None = None

    def _summarize_state(self, world_state: WorldState) -> str:
        """Create a structured summary of the current world state."""
        lines = []
        for entity in world_state.entities.values():
            attrs = ", ".join(f"{k}={v}" for k, v in entity.attributes.items())
            lines.append(f"- {entity.name} (ID: {entity.id}): {attrs}")
        return "\n".join(lines)

    def _format_last_decision(self) -> str:
        """Format last decision for context in prompt."""
        if not self.last_decision:
            return "None"

        return f"{self.last_decision.action} on {self.last_decision.target_entity_id}: {self.last_decision.reasoning[:50]}"

    def consult_oracle(self, world_state: WorldState) -> Decision | None:
        """Query the LLM for the next optimal action based on current state."""
        response = None
        try:
            available_actions = [action.value for action in ActionType]
            state_summary = self._summarize_state(world_state)
            last_decision_formatted = self._format_last_decision()

            system_instruction = f"""You are a home automation AI. Make ONE optimal decision per cycle.

ACTIONS: {', '.join(available_actions)}

PARAMS:
- SET_ATTRIBUTE: attribute_name, target_value (as string)
- TOGGLE_STATE: attribute_name (works on bool, ON/OFF, OPEN/CLOSED, etc.)
- INCREMENT/DECREMENT_VALUE: attribute_name, delta

PRIORITIES:
1. Safety: Lock doors, fix failures
2. Comfort: Light if lux<200, temp 20-24°C, charge if battery<20%
3. Energy: Turn off unused devices

RULES:
- Use exact entity UUIDs from state
- Return null if optimal
- Avoid repeating actions unless state changed

Last action: {last_decision_formatted}"""

            user_prompt = f"""Current state:
{state_summary}

Analyze and decide ONE optimal action. Return null if everything is optimal."""

            log_with_tui("info", "llm_api_call_starting", model=self.model)

            decision_schema = Decision.model_json_schema()

            system_message = Message(role="system", content=system_instruction)
            user_message = Message(role="user", content=user_prompt)

            response: ChatResponse = chat(
                model=self.model,
                messages=[system_message, user_message],
                format=decision_schema,
            )

            log_with_tui("info", "llm_api_call_completed", has_response=bool(response))

            if not response.message.content:
                log_with_tui("info", "llm_decision_none")
                return None

            content_dict = json.loads(response.message.content)

            if not content_dict:
                log_with_tui("info", "llm_decision_empty")
                self.last_decision = None
                return None

            decision = Decision.model_validate(content_dict)

            if decision.action == "null":
                log_with_tui("info", "llm_decision_empty")
                self.last_decision = None
                return None

            # Update last decision tracking
            self.last_decision = decision

            log_with_tui(
                "info",
                "llm_decision_made",
                action=decision.action,
                target=decision.target_entity_id,
                reasoning=decision.reasoning[:100],  # Truncate for logging
            )
            return decision

        except json.JSONDecodeError as e:
            raw_response = (
                response.message.content if response and response.message else "N/A"
            )
            log_with_tui(
                "error",
                "llm_json_parse_failed",
                error=str(e),
                response_text=raw_response[:200],
            )
            return None
        except Exception as e:
            raw_response = (
                response.message.content if response and response.message else "N/A"
            )
            log_with_tui(
                "error",
                "llm_consult_failed",
                error=str(e),
                response_text=raw_response[:200],
            )
            return None

    def reset_context(self):
        """Reset last decision context (useful for testing or new sessions)."""
        self.last_decision = None
        log_with_tui("info", "llm_context_reset")
