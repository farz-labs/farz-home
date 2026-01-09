import uuid
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tags: list[str]
    attributes: dict[str, str | bool | int | float]


class WorldState(BaseModel):
    entities: dict[str, Entity]

    def get_entities_by_tag(self, tag: str) -> list[Entity]:
        """Returns a list of entities that contain the specified tag."""

        return [entity for entity in self.entities.values() if tag in entity.tags]
