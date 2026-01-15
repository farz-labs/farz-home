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
            return "None (first decision)"

        return f"""Action: {self.last_decision.action}
Target Entity: {self.last_decision.target_entity_id}
Parameters: {json.dumps(self.last_decision.params.model_json_schema())}
Reasoning: {self.last_decision.reasoning}"""

    def consult_oracle(self, world_state: WorldState) -> Decision | None:
        """Query the LLM for the next optimal action based on current state."""
        response = None
        try:
            available_actions = [action.value for action in ActionType]
            state_summary = self._summarize_state(world_state)
            last_decision_formatted = self._format_last_decision()

            system_instruction = f"""You are an intelligent home automation AI that makes smart, context-aware decisions.

═══════════════════════════════════════════════════════════════
AVAILABLE ACTIONS:
═══════════════════════════════════════════════════════════════
{chr(10).join(f"  • {action}" for action in available_actions)}

═══════════════════════════════════════════════════════════════
ACTION PARAMETER GUIDELINES:
═══════════════════════════════════════════════════════════════
SET_ATTRIBUTE:
  • Use: attribute_name (string) and target_value (string)
  • Example: Set temperature to "22", brightness to "80"

TOGGLE_STATE:
  • Use: attribute_name only
  • Works on boolean: true ↔ false
  • Works on state pairs: ON ↔ OFF, LOCKED ↔ UNLOCKED, CLOSED ↔ OPEN, IDLE ↔ ACTIVE
  • Example: Toggle "state" attribute on a light

INCREMENT_VALUE / DECREMENT_VALUE:
  • Use: attribute_name and delta (numeric string)
  • Example: Increment "temperature" by "2", decrement "brightness" by "10"

═══════════════════════════════════════════════════════════════
DECISION PRIORITIES (in order):
═══════════════════════════════════════════════════════════════
1. Safety & Security:
   - Lock unsecured doors/windows when nobody home
   - Alert on critical sensor failures

2. Comfort & Efficiency:
   - Lighting: Turn on if lux < 200 (dark environment)
   - Temperature: Adjust if outside 20-24°C comfort range
   - Battery: Alert or charge if < 20%

3. Energy Optimization:
   - Turn off unnecessary devices
   - Reduce brightness when sufficient ambient light

═══════════════════════════════════════════════════════════════
IMPORTANT RULES:
═══════════════════════════════════════════════════════════════
✓ Use EXACT entity UUIDs from the current state
✓ Make ONE decision per cycle - choose the highest priority issue
✓ Return null (no action field) if all systems are optimal
✓ Avoid repeating the exact same action on the same entity unless state changed
✓ Provide clear, concise reasoning for your decision

═══════════════════════════════════════════════════════════════
LAST DECISION CONTEXT:
═══════════════════════════════════════════════════════════════
{last_decision_formatted}

Note: Avoid repeating this exact action unless the state has meaningfully changed.
"""

            user_prompt = f"""═══════════════════════════════════════════════════════════════
CURRENT HOME STATE:
═══════════════════════════════════════════════════════════════
{state_summary}

═══════════════════════════════════════════════════════════════
TASK:
═══════════════════════════════════════════════════════════════
Analyze the current state and decide on ONE optimal action.
Return null if no action is needed (everything is optimal).

Consider:
- What is the highest priority issue right now?
- Did the last decision address this, or has something changed?
- Will this action meaningfully improve the home state?
"""

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
