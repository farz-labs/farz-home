import time
from dataclasses import dataclass

from ollama import chat, Message

from core.models import WorldState, Decision
from core.logger import logger


@dataclass
class Correction:
    """Represents a detected user correction of an agent action."""

    action: Decision
    entity_id: str
    entity_name: str
    original_state: dict
    expected_state: dict
    actual_state: dict
    contradiction_time: float
    time_elapsed: float
    confidence: float


class CorrectionDetector:
    """Detects when users manually reverse or contradict agent actions."""

    def __init__(self, correction_window: int = 300):
        """
        Args:
            correction_window: Time window in seconds to check for contradictions (default 5 minutes)
        """
        self.correction_window = correction_window

    def detect_contradictions(
        self, world_state: WorldState, recent_actions: list[dict]
    ) -> list[Correction]:
        """
        Detect contradictions between recent actions and current state.

        Args:
            world_state: Current world state
            recent_actions: List of recent action records from Intelligence

        Returns:
            List of detected corrections
        """
        corrections = []
        current_time = time.time()

        for action_record in recent_actions:
            time_elapsed = current_time - action_record["timestamp"]

            # Skip if outside correction window
            if time_elapsed > self.correction_window:
                continue

            entity_id = action_record["entity_id"]
            entity = world_state.get_entity_by_id(entity_id)

            if not entity:
                continue

            expected_state = action_record["state_after"]
            actual_state = entity.attributes

            # Detect contradiction
            if self._is_contradicted(expected_state, actual_state):
                # Calculate confidence: faster reversal = higher confidence
                confidence = max(0.5, 1.0 - (time_elapsed / self.correction_window))

                correction = Correction(
                    action=action_record["decision"],
                    entity_id=str(entity_id),
                    entity_name=action_record["entity_name"],
                    original_state=action_record["state_before"],
                    expected_state=expected_state,
                    actual_state=dict(actual_state),
                    contradiction_time=current_time,
                    time_elapsed=time_elapsed,
                    confidence=confidence,
                )
                corrections.append(correction)

                logger.info(
                    "User correction detected",
                    entity=action_record["entity_name"],
                    action=action_record["decision"].action,
                    elapsed=f"{time_elapsed:.1f}s",
                    confidence=f"{confidence:.2f}",
                )

        return corrections

    def _is_contradicted(self, expected_state: dict, actual_state: dict) -> bool:
        """
        Check if actual state contradicts expected state.

        Rules:
        - Binary states (on/off, open/closed): exact opposite
        - Numeric values: >30% change from expected
        """
        # Check critical state attributes
        critical_attrs = ["state", "brightness", "temperature", "position"]

        for attr in critical_attrs:
            if attr not in expected_state:
                continue

            expected = expected_state[attr]
            actual = actual_state.get(attr)

            if actual is None:
                continue

            # Binary state contradiction
            if isinstance(expected, str):
                # Check for opposite states
                opposites = [
                    ("on", "off"),
                    ("off", "on"),
                    ("open", "closed"),
                    ("closed", "open"),
                    ("locked", "unlocked"),
                    ("unlocked", "locked"),
                    ("above_horizon", "below_horizon"),
                    ("below_horizon", "above_horizon"),
                ]

                for exp, act in opposites:
                    if expected.lower() == exp and actual.lower() == act:
                        return True

            # Numeric value contradiction (>30% change)
            elif isinstance(expected, (int, float)) and isinstance(
                actual, (int, float)
            ):
                if expected == 0:
                    # If expected was 0 and now non-zero, that's a change
                    if actual != 0:
                        return True
                else:
                    change_percent = abs((actual - expected) / expected)
                    if change_percent > 0.3:  # 30% threshold
                        return True

        return False


class LessonGenerator:
    """Generates lessons from user corrections using LLM."""

    def __init__(self, model: str = "llama3.2:latest"):
        self.model = model

    def generate_lesson(
        self, correction: Correction, world_state: WorldState
    ) -> str | None:
        """
        Generate a lesson from a user correction.

        Args:
            correction: Detected correction
            world_state: Current world state for context

        Returns:
            Lesson text or None if generation fails
        """
        try:
            # Build context summary
            context_entities = []
            for entity in world_state.entities.values():
                ha_entity_id = entity.attributes.get("ha_entity_id", "")
                if ha_entity_id:
                    domain = ha_entity_id.split(".")[0]
                    state = entity.attributes.get("state", "")
                    # Include context entities and the target entity's neighbors
                    if (
                        domain in ["sun", "weather"]
                        or entity.id == correction.action.target_entity_id
                    ):
                        context_entities.append(f"- {entity.name} ({domain}): {state}")

            context_summary = (
                "\n".join(context_entities)
                if context_entities
                else "No additional context"
            )

            # Format state changes
            state_changes = []
            for key in correction.expected_state:
                if key in correction.actual_state:
                    expected = correction.expected_state[key]
                    actual = correction.actual_state[key]
                    if expected != actual:
                        state_changes.append(f"{key}: {expected} → {actual}")

            changes_summary = (
                ", ".join(state_changes) if state_changes else "state reverted"
            )

            prompt = f"""Agent performed: {correction.action.action} on entity "{correction.entity_name}"
Reasoning: {correction.action.reasoning}

State before action: {self._format_state(correction.original_state)}
State immediately after action: {self._format_state(correction.expected_state)}
State {int(correction.time_elapsed)} seconds later: {self._format_state(correction.actual_state)}
Changes detected: {changes_summary}

World context at time of action:
{context_summary}

The user appears to have manually changed this entity. Generate a concise rule, preference, or lesson the agent should remember to avoid this situation in the future. Be specific but generalizable."""

            system_instruction = """You are a learning system for a home automation agent. When the agent takes an action that a user immediately reverses, you must infer why and generate a clear lesson.

Focus on:
1. What conditions led to the unwanted action
2. User preferences that were violated
3. Context patterns (time, other device states, etc.)

Output only the lesson as a single clear sentence, nothing else."""

            logger.debug("Generating lesson", entity=correction.entity_name)

            response = chat(
                model=self.model,
                messages=[
                    Message(role="system", content=system_instruction),
                    Message(role="user", content=prompt),
                ],
            )

            if response and response.message and response.message.content:
                lesson = response.message.content.strip()
                logger.info("Lesson generated", lesson=lesson[:100])
                return lesson

            return None

        except Exception as e:
            logger.error("Lesson generation failed", error=str(e))
            return None

    def _format_state(self, state: dict) -> str:
        """Format state dict for prompt."""
        items = [f"{k}={v}" for k, v in state.items()]
        return ", ".join(items[:5])  # Limit to 5 most relevant attributes
