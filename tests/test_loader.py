import os
import uuid

from core.loader import DataLoader


def test_yaml_data_loader():
    file_path = "./simulations/home.yaml"

    assert os.path.exists(file_path) is True

    data_loader = DataLoader()
    state = data_loader.load(file_path)

    assert state is not None

    living_room = state.entities[0]

    assert isinstance(living_room.id, uuid.UUID)
    assert living_room.name == "Living Room Light"
    assert living_room.tags[0] == "room:living"
