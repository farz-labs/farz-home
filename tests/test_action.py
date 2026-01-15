import uuid
from core.models import Entity, WorldState, Decision, DecisionParams
from core.actions import Dispatcher


def test_action():
    bulb_id = uuid.uuid4()
    light_bulb = Entity(
        id=bulb_id,
        name="Living Room Light",
        attributes={"brightness": 0.5, "is_on": False},
    )

    world = WorldState()
    world.entities[bulb_id] = light_bulb
    dispatcher = Dispatcher()

    decision = Decision(
        action="SET_ATTRIBUTE",
        target_entity_id=bulb_id,
        params=DecisionParams(attribute_name="brightness", target_value="10"),
        reasoning="Max brightness requested",
    )

    dispatcher.dispatch(world, decision)

    new_val = world.get_attribute_value(bulb_id, "brightness")

    assert new_val == 10


def test_toggle_state():
    bulb_id = uuid.uuid4()
    light_bulb = Entity(
        id=bulb_id,
        name="Living Room Light",
        attributes={"is_on": False},
    )

    world = WorldState()
    world.entities[bulb_id] = light_bulb
    dispatcher = Dispatcher()

    decision = Decision(
        action="TOGGLE_STATE",
        target_entity_id=bulb_id,
        params=DecisionParams(attribute_name="is_on", target_value="False"),
        reasoning="Toggle light state",
    )

    dispatcher.dispatch(world, decision)

    assert world.get_attribute_value(bulb_id, "is_on") is True

    dispatcher.dispatch(world, decision)

    assert world.get_attribute_value(bulb_id, "is_on") is False
