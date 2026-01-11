import random

from core.models import WorldState, Decision
from core.actions import Dispatcher
from core.utils import get_entity_by_name


class Intelligence:
    def __init__(self):
        self.dispatcher = Dispatcher.get_instance()

    def make_decision(self, world: WorldState) -> Decision | None:
        """
        The 'Brain' of the agent.
        Currently a stub that randomly decides to turn on the Living Room Light.
        """
        if random.random() > 0.3:
            return None

        try:
            target = get_entity_by_name(world, "Living Room Light")

            return Decision(
                action="SET_ATTRIBUTE",
                target_entity_id=target.id,
                params={"attribute": "brightness", "value": 100},
                reasoning="Simulated agent detected low light levels.",
            )
        except ValueError:
            return None

    def apply_action(self, world: WorldState, decision: Decision):
        self.dispatcher.dispatch(world=world, decision=decision)
