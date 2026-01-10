import uuid
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, bool | int | float | str] = Field(default_factory=dict)


class WorldState(BaseModel):
    entities: dict[uuid.UUID, Entity] = Field(default_factory=dict)

    def get_entities_by_tag(self, tag: str) -> list[Entity]:
        return [e for e in self.entities.values() if tag in e.tags]

    def get_attribute_value(self, entity_id: uuid.UUID, attribute: str):
        if entity := self.entities.get(entity_id):
            return entity.attributes.get(attribute)
        raise KeyError(f"Entity {entity_id} not found")

    def set_attribute_value(self, entity_id: uuid.UUID, attribute: str, value: float):
        if entity := self.entities.get(entity_id):
            entity.attributes[attribute] = value
            return
        raise KeyError(f"Entity {entity_id} not found")
