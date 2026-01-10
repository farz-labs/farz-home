import random

from core.models import WorldState, Decision
from core.utils import get_entity_by_name


def make_decision(world: WorldState) -> Decision | None:
    """
    The 'Brain' of the agent.
    Currently a stub that randomly decides to turn on the Living Room Light.
    """
    if random.random() > 0.3:
        return None

    try:
        # In the future, the LLM will look at world.entities to decide this.
        target = get_entity_by_name(world, "Living Room Light")

        return Decision(
            action="TURN_ON",
            target_entity_id=target.id,
            reasoning="Simulated agent detected low light levels.",
        )
    except ValueError:
        return None
