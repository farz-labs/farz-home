import uuid

from core.loader import DataLoader


def test_yaml_data_loader(tmp_path):
    d = tmp_path / "simulations"
    d.mkdir()
    p = d / "home.yaml"
    p.write_text("""
entities:
  - name: "Living Room Light"
    tags: ["room:living", "type:light"]
    attributes:
      state: "OFF"
    """)

    file_path = str(p)

    # 2. Load
    data_loader = DataLoader()
    result = data_loader.load(file_path)

    assert result is not None
    state, physics_data = result
    assert len(state.entities) == 1

    first_entity = list(state.entities.values())[0]

    assert isinstance(first_entity.id, uuid.UUID)
    assert first_entity.name == "Living Room Light"
    assert "room:living" in first_entity.tags
