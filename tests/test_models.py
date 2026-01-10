import uuid

from core.models import Entity, WorldState


def test_generic_entity_system():
    kitchen_light = Entity(
        name="Kitchen Light",
        tags=["location:kitchen", "type:light"],
        attributes={"is_open": False, "brightness": 80},
    )

    server_fan = Entity(
        name="Server Fan",
        tags=["location:server_room", "type:fan"],
        attributes={"rpm": 3000, "status": "active"},
    )

    assert isinstance(kitchen_light.id, uuid.UUID)
    assert kitchen_light.id != server_fan.id

    world = WorldState(
        entities={kitchen_light.id: kitchen_light, server_fan.id: server_fan}
    )

    kitchen_entities = world.get_entities_by_tag("location:kitchen")
    assert len(kitchen_entities) == 1
    assert kitchen_entities[0].name == "Kitchen Light"

    assert kitchen_entities[0].attributes["is_open"] is False
