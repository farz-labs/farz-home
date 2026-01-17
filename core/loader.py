import yaml
from pathlib import Path
from pydantic import ValidationError
from typing import Dict
from core.models import WorldState, Entity, Physics
from core.logger import app_logger


class DataLoader:
    def load(self, file_path: str | Path) -> tuple[WorldState, list[Physics]] | None:
        path = Path(file_path)
        if not path.exists():
            app_logger.error("error", "file_not_found", path=str(path))
            return None

        try:
            with path.open("r") as f:
                raw_data = yaml.safe_load(f)

            raw_entities_list = raw_data.get("entities", [])
            raw_physics_list = raw_data.get("physics", [])
            raw_global_attrs = raw_data.get("global_attributes", {})

            entity_map: Dict[str, Entity] = {}

            for item in raw_entities_list:
                entity = Entity(**item)
                entity_map[entity.id] = entity

            physics_data: list[Physics] = []

            for item in raw_physics_list:
                physics = Physics(**item)
                physics_data.append(physics)

            world_state = WorldState(
                entities=entity_map,
                global_attributes=raw_global_attrs
            )

            return world_state, physics_data

        except (ValidationError, yaml.YAMLError) as e:
            app_logger.error("error", "loader_failed", file=str(path), error=str(e))
            return None
