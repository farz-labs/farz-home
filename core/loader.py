import yaml
from pathlib import Path
from pydantic import ValidationError
from typing import Dict
from core.models import WorldState, Entity
from core.logger import app_logger


class DataLoader:
    def load(self, file_path: str | Path) -> WorldState | None:
        path = Path(file_path)
        if not path.exists():
            app_logger.critical("file_not_found", path=str(path))
            return None

        try:
            with path.open("r") as f:
                raw_data = yaml.safe_load(f)

            raw_entities_list = raw_data.get("entities", [])

            entity_map: Dict[str, Entity] = {}

            for item in raw_entities_list:
                entity = Entity(**item)
                entity_map[entity.id] = entity

            return WorldState(entities=entity_map)

        except (ValidationError, yaml.YAMLError) as e:
            app_logger.error("loader_failed", file=str(path), error=str(e))
            return None
