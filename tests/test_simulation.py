from unittest.mock import patch
from core.models import WorldState, Entity

from core.engine import run_living_room_simulation

@patch("core.engine.SimulationEngine")
def test_living_room_simulation(MockEngineClass):
    # Create a dummy world
    light = Entity(name="Living Room Light", tags=["light"], attributes={"brightness": 0.0})

    world = WorldState(entities={light.id: light})

    mock_engine_instance = MockEngineClass.return_value

    run_living_room_simulation(world)

    MockEngineClass.assert_called_with(step=0.5)

    assert mock_engine_instance.run_loop.called is True
    
    _, kwargs = mock_engine_instance.run_loop.call_args
    
    assert kwargs['world_state'] == world
    assert callable(kwargs['update_fn'])
    assert callable(kwargs['log_fn'])

    actual_update_fn = kwargs['update_fn']
    
    # Run the logic once manually
    actual_update_fn(world)
    
    # Check if the world actually changed (0.0 -> 0.1)
    # This proves the "partial" was constructed correctly
    updated_brightness = world.get_attribute_value(light.id, "brightness")
    assert updated_brightness == 0.1