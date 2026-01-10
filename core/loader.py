import yaml

from pathlib import Path
from pydantic import ValidationError

from core.models import WorldState
from core.logger import app_logger


class DataLoader:
    def load(self, file_path: str | Path) -> WorldState | None:
        path = Path(file_path)
        if not path.exists():
            app_logger.critical(f"File not exists in the path {file_path}")
            return None

        try:
            with path.open("r") as f:
                config_data = yaml.safe_load(f)

            return WorldState.model_validate(config_data)

        except (ValidationError, yaml.YAMLError) as e:
            app_logger.error(f"Failed to load world state from {file_path}: {e}")
            return None
