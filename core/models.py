import uuid
from pydantic import BaseModel, Field


class Entity(BaseModel):
    id: uuid.UUID = Field(default_factory=uuid.uuid4)
    name: str
    tags: list[str] = Field(default_factory=list)
    attributes: dict[str, bool | int | float | str] = Field(default_factory=dict)


class WorldState(BaseModel):
    entities: list[Entity]

    def get_entities_by_tag(self, tag: str) -> list[Entity]:
        """Returns a list of entities that contain the specified tag."""
        return [e for e in self.entities if tag in e.tags]
