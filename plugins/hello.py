from core.plugins import BasePlugin
from core.logger import log_with_tui
from core.models import Physics


class HelloPlugin(BasePlugin):
    def __init__(self):
        super().__init__()

    @property
    def name(self) -> str:
        return "Hello Plugin"

    def register_actions(self, dispatcher):
        # Example action handler with correct signature
        def say_hello_action(world, target_id, params):
            log_with_tui("info", "hello_action_called", target=str(target_id))
        
        dispatcher.register("SAY_HELLO", say_hello_action)

    def register_physics(self, physics_engine):
        """Example: Add custom physics rule programmatically."""
        # Add a custom physics rule that makes lights generate extra heat
        physics_engine.add_physics_rule(
            Physics(
                target_tag="device:light",
                attribute="plugin_custom_heat",
                delta=0.02,
                condition="state == \"ON\" and brightness > 50"
            )
        )
        
        log_with_tui("info", "plugin_physics_registered", name=self.name)

    def on_startup(self, state):
        super().on_startup(state)
        log_with_tui("info", "plugin_started", name=self.name, entities=len(state.entities))
