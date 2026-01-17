import uuid
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, bool | int | float | str] = Field(default_factory=dict)


class Physics(BaseModel):
    target_tag: str
    attribute: str
    delta: float
    condition: str | None = None


class WorldState(BaseModel):
    entities: dict[uuid.UUID, Entity] = Field(default_factory=dict)
    global_attributes: dict[str, float | bool | str] = Field(default_factory=dict)

    def get_entities_by_tag(self, tag: str) -> list[Entity]:
        # Handle virtual 'global' entity
        if tag == "global":
            return [
                Entity(
                    id=uuid.UUID("00000000-0000-0000-0000-000000000000"),
                    name="__global__",
                    tags=["global"],
                    attributes=self.global_attributes,
                )
            ]
        return [e for e in self.entities.values() if tag in e.tags]

    def get_entity_by_id(self, entity_id):
        return self.entities.get(entity_id)

    def get_attribute_value(self, entity_id, attribute):
        entity = self.get_entity_by_id(entity_id)
        if entity:
            return entity.attributes.get(attribute)
        raise KeyError(f"Entity {entity_id} not found")

    def set_attribute_value(self, entity_id, attribute, value):
        entity = self.get_entity_by_id(entity_id)
        if entity:
            entity.attributes[attribute] = value
            return
        raise KeyError(f"Entity {entity_id} not found")


class DecisionParams(BaseModel):
    attribute_name: str | None = Field(
        None, description="Name of the attribute to change"
    )
    target_value: str | None = Field(
        None, description="The value to set (convert to int/float/bool later)"
    )
    delta: float | None = Field(None, description="Amount to increment or decrement")


class Decision(BaseModel):
    action: str
    target_entity_id: uuid.UUID
    params: DecisionParams
    reasoning: str
