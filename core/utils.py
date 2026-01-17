from core.models import WorldState, Entity
from core.logger import log_with_tui


def get_entity_by_name(world: WorldState, name: str) -> Entity:
    """
    O(N) lookup to find an entity by its human-readable name.
    Note: In high-scale systems, we would use a name->id index to make this O(1).
    """
    for entity in world.entities.values():
        if entity.name == name:
            return entity

    raise ValueError(f"Entity with name '{name}' not found in WorldState.")


def increment_attribute(
    world: WorldState,
    entity_name: str,
    attribute_name: str,
    delta: float = 0.1,
    default: float = 0.0,
) -> None:
    """
    Safely increments a numeric attribute.
    Initialize with 'default' if the attribute is missing.
    """
    entity = get_entity_by_name(world, entity_name)

    current = world.get_attribute_value(entity.id, attribute_name)

    if current is None:
        current = default
        log_with_tui(
            "debug",
            "attribute_auto_init",
            entity=entity_name,
            attribute=attribute_name,
            default=default,
        )

    if not isinstance(current, (int, float)):
        raise TypeError(
            f"Cannot increment attribute '{attribute_name}' on '{entity_name}'. "
            f"Current value is type {type(current).__name__}: {current!r}"
        )

    new_value = current + delta
    world.set_attribute_value(entity.id, attribute_name, new_value)
